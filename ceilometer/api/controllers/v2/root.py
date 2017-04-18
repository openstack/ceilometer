#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Huawei Technologies Co., Ltd.
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

from keystoneauth1 import exceptions
from oslo_config import cfg
from oslo_log import log
from oslo_utils import strutils
import pecan

from ceilometer.api.controllers.v2 import capabilities
from ceilometer.api.controllers.v2 import meters
from ceilometer.api.controllers.v2 import query
from ceilometer.api.controllers.v2 import resources
from ceilometer.api.controllers.v2 import samples
from ceilometer.i18n import _
from ceilometer import keystone_client


API_OPTS = [
    cfg.BoolOpt('gnocchi_is_enabled',
                help=('Set True to disable resource/meter/sample URLs. '
                      'Default autodetection by querying keystone.')),
    cfg.BoolOpt('aodh_is_enabled',
                help=('Set True to redirect alarms URLs to aodh. '
                      'Default autodetection by querying keystone.')),
    cfg.StrOpt('aodh_url',
               help=('The endpoint of Aodh to redirect alarms URLs '
                     'to Aodh API. Default autodetection by querying '
                     'keystone.')),
    cfg.BoolOpt('panko_is_enabled',
                help=('Set True to redirect events URLs to Panko. '
                      'Default autodetection by querying keystone.')),
    cfg.StrOpt('panko_url',
               help=('The endpoint of Panko to redirect events URLs '
                     'to Panko API. Default autodetection by querying '
                     'keystone.')),
]

LOG = log.getLogger(__name__)


def gnocchi_abort():
    pecan.abort(410, ("This telemetry installation is configured to use "
                      "Gnocchi. Please use the Gnocchi API available on "
                      "the metric endpoint to retrieve data."))


def aodh_abort():
    pecan.abort(410, _("alarms URLs is unavailable when Aodh is "
                       "disabled or unavailable."))


def _redirect(url):
    pecan.redirect(location=url + pecan.request.path_qs,
                   code=308)


class QueryController(object):
    def __init__(self, gnocchi_is_enabled=False,
                 aodh_url=None):
        self.gnocchi_is_enabled = gnocchi_is_enabled
        self.aodh_url = aodh_url

    @pecan.expose()
    def _lookup(self, kind, *remainder):
        if kind == 'alarms' and self.aodh_url:
            _redirect(self.aodh_url)
        elif kind == 'alarms':
            aodh_abort()
        elif kind == 'samples' and self.gnocchi_is_enabled:
            gnocchi_abort()
        elif kind == 'samples':
            return query.QuerySamplesController(), remainder
        else:
            pecan.abort(404)


class V2Controller(object):
    """Version 2 API controller root."""

    capabilities = capabilities.CapabilitiesController()

    def __init__(self):
        self._gnocchi_is_enabled = None
        self._aodh_is_enabled = None
        self._aodh_url = None
        self._panko_is_enabled = None
        self._panko_url = None

    @property
    def gnocchi_is_enabled(self):
        if self._gnocchi_is_enabled is None:
            if pecan.request.cfg.api.gnocchi_is_enabled is not None:
                self._gnocchi_is_enabled = (
                    pecan.request.cfg.api.gnocchi_is_enabled)

            elif ("gnocchi" not in pecan.request.cfg.meter_dispatchers
                  or "database" in pecan.request.cfg.meter_dispatchers):
                self._gnocchi_is_enabled = False
            else:
                try:
                    catalog = keystone_client.get_service_catalog(
                        keystone_client.get_client(pecan.request.cfg))
                    catalog.url_for(service_type='metric')
                except exceptions.EndpointNotFound:
                    self._gnocchi_is_enabled = False
                except exceptions.ClientException:
                    LOG.warning("Can't connect to keystone, assuming "
                                "gnocchi is disabled and retry later")
                else:
                    self._gnocchi_is_enabled = True
                    LOG.warning("ceilometer-api started with gnocchi "
                                "enabled. The resources/meters/samples "
                                "URLs are disabled.")
        return self._gnocchi_is_enabled

    @property
    def aodh_url(self):
        if self._aodh_url is None:
            if pecan.request.cfg.api.aodh_is_enabled is False:
                self._aodh_url = ""
            elif pecan.request.cfg.api.aodh_url is not None:
                self._aodh_url = self._normalize_url(
                    pecan.request.cfg.api.aodh_url)
            else:
                try:
                    catalog = keystone_client.get_service_catalog(
                        keystone_client.get_client(pecan.request.cfg))
                    self._aodh_url = self._normalize_url(
                        catalog.url_for(service_type='alarming'))
                except exceptions.EndpointNotFound:
                    self._aodh_url = ""
                except exceptions.ClientException:
                    LOG.warning("Can't connect to keystone, assuming aodh "
                                "is disabled and retry later.")
                else:
                    LOG.warning("ceilometer-api started with aodh "
                                "enabled. Alarms URLs will be redirected "
                                "to aodh endpoint.")
        return self._aodh_url

    @property
    def panko_url(self):
        if self._panko_url is None:
            if pecan.request.cfg.api.panko_is_enabled is False:
                self._panko_url = ""
            elif pecan.request.cfg.api.panko_url is not None:
                self._panko_url = self._normalize_url(
                    pecan.request.cfg.api.panko_url)
            else:
                try:
                    catalog = keystone_client.get_service_catalog(
                        keystone_client.get_client(pecan.request.cfg))
                    self._panko_url = self._normalize_url(
                        catalog.url_for(service_type='event'))
                except exceptions.EndpointNotFound:
                    self._panko_url = ""
                except exceptions.ClientException:
                    LOG.warning(
                        "Can't connect to keystone, assuming Panko "
                        "is disabled and retry later.")
                else:
                    LOG.warning("ceilometer-api started with Panko "
                                "enabled. Events URLs will be redirected "
                                "to Panko endpoint.")
        return self._panko_url

    @pecan.expose()
    def _lookup(self, kind, *remainder):
        if (kind in ['meters', 'resources', 'samples']
                and self.gnocchi_is_enabled):
            if kind == 'meters' and pecan.request.method == 'POST':
                direct = pecan.request.params.get('direct', '')
                if strutils.bool_from_string(direct):
                    pecan.abort(400, _('direct option cannot be true when '
                                       'Gnocchi is enabled.'))
                return meters.MetersController(), remainder
            gnocchi_abort()
        elif kind == 'meters':
            return meters.MetersController(), remainder
        elif kind == 'resources':
            return resources.ResourcesController(), remainder
        elif kind == 'samples':
            return samples.SamplesController(), remainder
        elif kind == 'query':
            return QueryController(
                gnocchi_is_enabled=self.gnocchi_is_enabled,
                aodh_url=self.aodh_url,
            ), remainder
        elif kind == 'alarms' and (not self.aodh_url):
            aodh_abort()
        elif kind == 'alarms' and self.aodh_url:
            _redirect(self.aodh_url)
        elif kind == 'events' and self.panko_url:
            return _redirect(self.panko_url)
        elif kind == 'event_types' and self.panko_url:
            return _redirect(self.panko_url)
        else:
            pecan.abort(404)

    @staticmethod
    def _normalize_url(url):
        if url.endswith("/"):
            return url[:-1]
        return url
