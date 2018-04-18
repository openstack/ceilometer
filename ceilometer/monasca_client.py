# Copyright 2015 Hewlett-Packard Company
# (c) Copyright 2018 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from monascaclient import client
from monascaclient import exc
from oslo_log import log
import tenacity

from ceilometer.i18n import _
from ceilometer import keystone_client

LOG = log.getLogger(__name__)


class MonascaException(Exception):
    def __init__(self, message=''):
        msg = 'An exception is raised from Monasca: ' + message
        super(MonascaException, self).__init__(msg)


class MonascaServiceException(Exception):
    def __init__(self, message=''):
        msg = 'Monasca service is unavailable: ' + message
        super(MonascaServiceException, self).__init__(msg)


class MonascaInvalidParametersException(Exception):
    code = 400

    def __init__(self, message=''):
        msg = 'Request cannot be handled by Monasca: ' + message
        super(MonascaInvalidParametersException, self).__init__(msg)


class Client(object):
    """A client which gets information via python-monascaclient."""

    def __init__(self, conf, parsed_url):
        self.conf = conf
        self._retry_interval = conf.monasca.client_retry_interval
        self._max_retries = conf.monasca.client_max_retries or 1
        self._enable_api_pagination = conf.monasca.enable_api_pagination
        # NOTE(zqfan): There are many concurrency requests while using
        # Ceilosca, to save system resource, we don't retry too many times.
        if self._max_retries < 0 or self._max_retries > 10:
            LOG.warning('Reduce max retries from %s to 10',
                        self._max_retries)
            self._max_retries = 10

        monasca_auth_group = conf.monasca.auth_section
        session = keystone_client.get_session(conf, group=monasca_auth_group)

        self._endpoint = parsed_url.netloc + parsed_url.path
        LOG.info(_("monasca_client: using %s as Monasca endpoint") %
                 self._endpoint)

        self._get_client(session)

    def _get_client(self, session):
        self._mon_client = client.Client(self.conf.monasca.clientapi_version,
                                         endpoint=self._endpoint,
                                         session=session)

    def call_func(self, func, **kwargs):
        """General method for calling any Monasca API function."""
        @tenacity.retry(
            wait=tenacity.wait_fixed(self._retry_interval),
            stop=tenacity.stop_after_attempt(self._max_retries),
            retry=(tenacity.retry_if_exception_type(MonascaServiceException) |
                   tenacity.retry_if_exception_type(MonascaException)))
        def _inner():
            try:
                return func(**kwargs)
            except (exc.http.InternalServerError,
                    exc.http.ServiceUnavailable,
                    exc.http.BadGateway,
                    exc.connection.ConnectionError) as e:
                LOG.exception(e)
                msg = '%s: %s' % (e.__class__.__name__, e)
                raise MonascaServiceException(msg)
            except exc.http.HttpError as e:
                LOG.exception(e)
                msg = '%s: %s' % (e.__class__.__name__, e)
                status_code = e.http_status
                if not isinstance(status_code, int):
                    status_code = 500
                if 400 <= status_code < 500:
                    raise MonascaInvalidParametersException(msg)
                else:
                    raise MonascaException(msg)
            except Exception as e:
                LOG.exception(e)
                msg = '%s: %s' % (e.__class__.__name__, e)
                raise MonascaException(msg)

        return _inner()

    def metrics_create(self, **kwargs):
        return self.call_func(self._mon_client.metrics.create,
                              **kwargs)
