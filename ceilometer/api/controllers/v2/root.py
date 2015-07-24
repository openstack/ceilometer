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

from keystoneclient.openstack.common.apiclient import exceptions
from oslo_config import cfg
from oslo_log import log
import pecan

from ceilometer.api.controllers.v2 import alarms
from ceilometer.api.controllers.v2 import capabilities
from ceilometer.api.controllers.v2 import events
from ceilometer.api.controllers.v2 import meters
from ceilometer.api.controllers.v2 import query
from ceilometer.api.controllers.v2 import resources
from ceilometer.api.controllers.v2 import samples
from ceilometer.i18n import _LW
from ceilometer import keystone_client


API_OPTS = [
    cfg.BoolOpt('gnocchi_is_enabled',
                default=None,
                help=('Set True to disable resource/meter/sample URLs. '
                      'Default autodetection by querying keystone.')),
]

cfg.CONF.register_opts(API_OPTS, group='api')
cfg.CONF.import_opt('dispatcher', 'ceilometer.dispatcher')

LOG = log.getLogger(__name__)


def gnocchi_abort():
    pecan.abort(410, ("This telemetry installation is configured to use "
                      "Gnocchi. Please use the Gnocchi API available on "
                      "the metric endpoint to retreive data."))


class QueryController(object):
    def __init__(self, gnocchi_is_enabled=False):
        self.gnocchi_is_enabled = gnocchi_is_enabled

    @pecan.expose()
    def _lookup(self, kind, *remainder):
        if kind == 'alarms':
            return query.QueryAlarmsController(), remainder
        elif kind == 'samples' and self.gnocchi_is_enabled:
            gnocchi_abort()
        elif kind == 'samples':
            return query.QuerySamplesController(), remainder
        else:
            pecan.abort(404)


class V2Controller(object):
    """Version 2 API controller root."""

    event_types = events.EventTypesController()
    events = events.EventsController()
    capabilities = capabilities.CapabilitiesController()

    def __init__(self):
        self._gnocchi_is_enabled = None

    @property
    def gnocchi_is_enabled(self):
        if self._gnocchi_is_enabled is None:
            if cfg.CONF.api.gnocchi_is_enabled is not None:
                self._gnocchi_is_enabled = cfg.CONF.api.gnocchi_is_enabled

            elif ("gnocchi" not in cfg.CONF.dispatcher
                  or "database" in cfg.CONF.dispatcher):
                self._gnocchi_is_enabled = False
            else:
                try:
                    ks = keystone_client.get_client()
                    ks.service_catalog.url_for(service_type='metric')
                except exceptions.EndpointNotFound:
                    self._gnocchi_is_enabled = False
                except exceptions.ClientException:
                    LOG.warn(_LW("Can't connect to keystone, assuming gnocchi "
                                 "is disabled and retry later"))
                    return False
                else:
                    self._gnocchi_is_enabled = True
                    LOG.warn(_LW("ceilometer-api started with gnocchi "
                                 "enabled. The resources/meters/samples "
                                 "URLs are disabled."))
        return self._gnocchi_is_enabled

    @pecan.expose()
    def _lookup(self, kind, *remainder):
        if (kind in ['meters', 'resources', 'samples']
                and self.gnocchi_is_enabled):
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
            ), remainder
        elif kind == 'alarms':
            return alarms.AlarmsController(), remainder
        else:
            pecan.abort(404)
