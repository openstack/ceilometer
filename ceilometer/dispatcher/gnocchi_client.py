#
# Copyright 2015 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import functools
import json

from oslo_log import log
import requests
from requests import adapters
import retrying
from six.moves.urllib import parse as urlparse
import socket

from ceilometer.i18n import _
from ceilometer import keystone_client

LOG = log.getLogger(__name__)


class UnexpectedError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class NoSuchMetric(Exception):
    pass


class MetricAlreadyExists(Exception):
    pass


class NoSuchResource(Exception):
    pass


class ResourceAlreadyExists(Exception):
    pass


def retry_if_authentication_error(exception):
    return isinstance(exception, AuthenticationError)


def maybe_retry_if_authentication_error():
    return retrying.retry(retry_on_exception=retry_if_authentication_error,
                          wait_fixed=2000,
                          stop_max_delay=60000)


class CustomHTTPAdapter(adapters.HTTPAdapter):
    """CustomHTTPAdapter

    This HTTPAdapter doesn't trigger some urllib3 issues.
    urllib3 doesn't put back connection to the pool when
    some errors occurs like a simple ECONNREFUSED.

    This HTTPAdapter workaround this by enforcing preloading
    of the response. When enabled, urllib3 releases the connection
    to the pool immediately after its usage, and doesn't trigger the
    issue.

    By enforcing preloading, this break some requests
    features (like stream) that we didn't use into our GnocchiClient

    * https://github.com/shazow/urllib3/issues/659
    * https://github.com/shazow/urllib3/issues/651
    * https://github.com/shazow/urllib3/issues/644
    * https://github.com/kennethreitz/requests/issues/2687

    We could remove this when requests 2.8.0 will be released
    """
    def send(self, request, stream=False, timeout=None, verify=True, cert=None,
             proxies=None):
        conn = self.get_connection(request.url, proxies)
        self.cert_verify(conn, request.url, verify, cert)
        url = self.request_url(request, proxies)
        self.add_headers(request)

        chunked = not (request.body is None or
                       'Content-Length' in request.headers)

        if isinstance(timeout, tuple):
            try:
                connect, read = timeout
                timeout = adapters.TimeoutSauce(connect=connect, read=read)
            except ValueError as e:
                # this may raise a string formatting error.
                err = ("Invalid timeout {0}. Pass a (connect, read) "
                       "timeout tuple, or a single float to set "
                       "both timeouts to the same value".format(timeout))
                raise ValueError(err)
        else:
            timeout = adapters.TimeoutSauce(connect=timeout, read=timeout)

        try:
            if not chunked:
                resp = conn.urlopen(
                    method=request.method,
                    url=url,
                    body=request.body,
                    headers=request.headers,
                    redirect=False,
                    assert_same_host=False,
                    preload_content=True,  # NOTE(sileht): workaround
                    decode_content=False,
                    retries=self.max_retries,
                    timeout=timeout
                )

            # Send the request.
            else:
                if hasattr(conn, 'proxy_pool'):
                    conn = conn.proxy_pool

                low_conn = conn._get_conn(
                    timeout=adapters.DEFAULT_POOL_TIMEOUT)

                try:
                    low_conn.putrequest(request.method,
                                        url,
                                        skip_accept_encoding=True)

                    for header, value in request.headers.items():
                        low_conn.putheader(header, value)

                    low_conn.endheaders()

                    for i in request.body:
                        low_conn.send(hex(len(i))[2:].encode('utf-8'))
                        low_conn.send(b'\r\n')
                        low_conn.send(i)
                        low_conn.send(b'\r\n')
                    low_conn.send(b'0\r\n\r\n')

                    r = low_conn.getresponse()
                    resp = adapters.HTTPResponse.from_httplib(
                        r,
                        pool=conn,
                        connection=low_conn,
                        preload_content=True,  # NOTE(sileht): workaround
                        decode_content=False
                    )
                except Exception:
                    # If we hit any problems here, clean up the connection.
                    # Then, reraise so that we can handle the actual exception.
                    low_conn.close()
                    raise

        except (adapters.ProtocolError, socket.error) as err:
            raise adapters.ConnectionError(err, request=request)

        except adapters.MaxRetryError as e:
            if isinstance(e.reason, adapters.ConnectTimeoutError):
                raise adapters.ConnectTimeout(e, request=request)

            if isinstance(e.reason, adapters.ResponseError):
                raise adapters.RetryError(e, request=request)

            raise adapters.ConnectionError(e, request=request)

        except adapters._ProxyError as e:
            raise adapters.ProxyError(e)

        except (adapters._SSLError, adapters._HTTPError) as e:
            if isinstance(e, adapters._SSLError):
                raise adapters.SSLError(e, request=request)
            elif isinstance(e, adapters.ReadTimeoutError):
                raise adapters.ReadTimeout(e, request=request)
            else:
                raise

        return self.build_response(request, resp)


class GnocchiSession(object):
    def __init__(self):
        self._session = requests.session()
        # NOTE(sileht): wait when the pool is empty
        # instead of raising errors.
        adapter = CustomHTTPAdapter(pool_block=True)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        self.post = functools.partial(self._do_method, method='post')
        self.patch = functools.partial(self._do_method, method='patch')

    def _do_method(self, *args, **kwargs):
        method = kwargs.pop('method')
        try:
            response = getattr(self._session, method)(*args, **kwargs)
        except requests.ConnectionError as e:
            raise UnexpectedError("Connection error: %s " % e)

        if response.status_code == 401:
            LOG.info("Authentication failure, retrying...")
            raise AuthenticationError()

        return response


class Client(object):
    def __init__(self, url):
        self._gnocchi_url = url.rstrip("/")
        self._ks_client = keystone_client.get_client()
        self._session = GnocchiSession()

    def _get_headers(self, content_type="application/json"):
        return {
            'Content-Type': content_type,
            'X-Auth-Token': self._ks_client.auth_token,
        }

    @maybe_retry_if_authentication_error()
    def post_measure(self, resource_type, resource_id, metric_name,
                     measure_attributes):
        r = self._session.post("%s/v1/resource/%s/%s/metric/%s/measures"
                               % (self._gnocchi_url, resource_type,
                                  urlparse.quote(resource_id, safe=""),
                                  metric_name),
                               headers=self._get_headers(),
                               data=json.dumps(measure_attributes))

        if r.status_code == 404:
            LOG.debug("The metric %(metric_name)s of "
                      "resource %(resource_id)s doesn't exists: "
                      "%(status_code)d",
                      {'metric_name': metric_name,
                       'resource_id': resource_id,
                       'status_code': r.status_code})
            raise NoSuchMetric
        elif r.status_code // 100 != 2:
            raise UnexpectedError(
                _("Fail to post measure on metric %(metric_name)s of "
                  "resource %(resource_id)s with status: "
                  "%(status_code)d: %(msg)s") %
                {'metric_name': metric_name,
                 'resource_id': resource_id,
                 'status_code': r.status_code,
                 'msg': r.text})
        else:
            LOG.debug("Measure posted on metric %s of resource %s",
                      metric_name, resource_id)

    @maybe_retry_if_authentication_error()
    def create_resource(self, resource_type, resource):
        r = self._session.post("%s/v1/resource/%s"
                               % (self._gnocchi_url, resource_type),
                               headers=self._get_headers(),
                               data=json.dumps(resource))

        if r.status_code == 409:
            LOG.debug("Resource %s already exists", resource['id'])
            raise ResourceAlreadyExists

        elif r.status_code // 100 != 2:
            raise UnexpectedError(
                _("Resource %(resource_id)s creation failed with "
                  "status: %(status_code)d: %(msg)s") %
                {'resource_id': resource['id'],
                 'status_code': r.status_code,
                 'msg': r.text})
        else:
            LOG.debug("Resource %s created", resource['id'])

    @maybe_retry_if_authentication_error()
    def update_resource(self, resource_type, resource_id,
                        resource_extra):
        r = self._session.patch(
            "%s/v1/resource/%s/%s"
            % (self._gnocchi_url, resource_type,
               urlparse.quote(resource_id, safe="")),
            headers=self._get_headers(),
            data=json.dumps(resource_extra))

        if r.status_code // 100 != 2:
            raise UnexpectedError(
                _("Resource %(resource_id)s update failed with "
                  "status: %(status_code)d: %(msg)s") %
                {'resource_id': resource_id,
                 'status_code': r.status_code,
                 'msg': r.text})
        else:
            LOG.debug("Resource %s updated", resource_id)

    @maybe_retry_if_authentication_error()
    def create_metric(self, resource_type, resource_id, metric_name,
                      archive_policy):
        params = {metric_name: archive_policy}
        r = self._session.post("%s/v1/resource/%s/%s/metric"
                               % (self._gnocchi_url, resource_type,
                                  urlparse.quote(resource_id, safe="")),
                               headers=self._get_headers(),
                               data=json.dumps(params))
        if r.status_code == 409:
            LOG.debug("Metric %s of resource %s already exists",
                      metric_name, resource_id)
            raise MetricAlreadyExists

        elif r.status_code // 100 != 2:
            raise UnexpectedError(
                _("Fail to create metric %(metric_name)s of "
                  "resource %(resource_id)s with status: "
                  "%(status_code)d: %(msg)s") %
                {'metric_name': metric_name,
                 'resource_id': resource_id,
                 'status_code': r.status_code,
                 'msg': r.text})
        else:
            LOG.debug("Metric %s of resource %s created",
                      metric_name, resource_id)
