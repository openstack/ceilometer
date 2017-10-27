#
# Copyright 2015 Intel Corp.
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

import itertools
import pkg_resources

from oslo_config import cfg
from oslo_log import log
from oslo_utils import netutils
import six

from ceilometer.agent import plugin_base
from ceilometer import declarative
from ceilometer.hardware import inspector as insloader
from ceilometer.hardware.pollsters import util
from ceilometer.i18n import _
from ceilometer import sample

OPTS = [
    cfg.StrOpt('meter_definitions_file',
               default="snmp.yaml",
               help="Configuration file for defining hardware snmp meters."
               ),
]

LOG = log.getLogger(__name__)


class MeterDefinition(object):
    required_fields = ['name', 'unit', 'type']

    def __init__(self, definition_cfg):
        self.cfg = definition_cfg
        for fname, fval in self.cfg.items():
            if (isinstance(fname, six.string_types) and
                (fname in self.required_fields or
                 fname.endswith('_inspector'))):
                setattr(self, fname, fval)
            else:
                LOG.warning("Ignore unrecognized field %s", fname)
        for fname in self.required_fields:
            if not getattr(self, fname, None):
                raise declarative.MeterDefinitionException(
                    _("Missing field %s") % fname, self.cfg)
        if self.type not in sample.TYPES:
            raise declarative.MeterDefinitionException(
                _("Unrecognized type value %s") % self.type, self.cfg)


class GenericHardwareDeclarativePollster(plugin_base.PollsterBase):
    CACHE_KEY = 'hardware.generic'
    mapping = None

    def __init__(self, conf):
        super(GenericHardwareDeclarativePollster, self).__init__(conf)
        self.inspectors = {}

    def _update_meter_definition(self, definition):
        self.meter_definition = definition
        self.cached_inspector_params = {}

    @property
    def default_discovery(self):
        return 'tripleo_overcloud_nodes'

    @staticmethod
    def _parse_resource(res):
        """Parse resource from discovery.

        Either URL can be given or dict. Dict has to contain at least
        keys 'resource_id' and 'resource_url', all the dict keys will be stored
        as metadata.

        :param res: URL or dict containing all resource info.
        :return: parsed_url, resource_id, metadata Returns parsed URL used for
            SNMP query, unique identifier of the resource and metadata
            of the resource.
        """
        parsed_url, resource_id, metadata = (None, None, None)
        if isinstance(res, dict):
            if 'resource_url' not in res or 'resource_id' not in res:
                LOG.error('Passed resource dict must contain keys '
                          'resource_id and resource_url.')
            else:
                metadata = res
                parsed_url = netutils.urlsplit(res['resource_url'])
                resource_id = res['resource_id']
        else:
            metadata = {}
            parsed_url = netutils.urlsplit(res)
            resource_id = res

        return parsed_url, resource_id, metadata

    def _get_inspector(self, parsed_url):
        if parsed_url.scheme not in self.inspectors:
            try:
                driver = insloader.get_inspector(parsed_url)
                self.inspectors[parsed_url.scheme] = driver
            except Exception as err:
                LOG.exception("Cannot load inspector %(name)s: %(err)s",
                              dict(name=parsed_url.scheme,
                                   err=err))
                raise
        return self.inspectors[parsed_url.scheme]

    def get_samples(self, manager, cache, resources=None):
        """Return an iterable of Sample instances from polling the resources.

        :param manager: The service manager invoking the plugin
        :param cache: A dictionary for passing data between plugins
        :param resources: end point to poll data from
        """
        resources = resources or []
        h_cache = cache.setdefault(self.CACHE_KEY, {})
        sample_iters = []

        # Get the meter identifiers to poll
        identifier = self.meter_definition.name

        for resource in resources:
            parsed_url, res, extra_metadata = self._parse_resource(resource)
            if parsed_url is None:
                LOG.error("Skip invalid resource %s", resource)
                continue
            ins = self._get_inspector(parsed_url)
            try:
                # Call hardware inspector to poll for the data
                i_cache = h_cache.setdefault(res, {})

                # Prepare inspector parameters and cache it for performance
                param_key = parsed_url.scheme + '.' + identifier
                inspector_param = self.cached_inspector_params.get(param_key)
                if not inspector_param:
                    param = getattr(self.meter_definition,
                                    parsed_url.scheme + '_inspector', {})
                    inspector_param = ins.prepare_params(param)
                    self.cached_inspector_params[param_key] = inspector_param

                if identifier not in i_cache:
                    i_cache[identifier] = list(ins.inspect_generic(
                        host=parsed_url,
                        cache=i_cache,
                        extra_metadata=extra_metadata,
                        param=inspector_param))
                # Generate samples
                if i_cache[identifier]:
                    sample_iters.append(self.generate_samples(
                        parsed_url,
                        i_cache[identifier]))
            except Exception as err:
                msg = ('inspector call failed for %(ident)s '
                       'host %(host)s: %(err)s' %
                       dict(ident=identifier,
                            host=parsed_url.hostname,
                            err=err))
                if "timeout" in str(err):
                    LOG.warning(msg)
                else:
                    LOG.exception(msg)
        return itertools.chain(*sample_iters)

    def generate_samples(self, host_url, data):
        """Generate a list of Sample from the data returned by inspector

        :param host_url: host url of the endpoint
        :param data: list of data returned by the corresponding inspector
        """
        samples = []
        definition = self.meter_definition
        for (value, metadata, extra) in data:
            s = util.make_sample_from_host(host_url,
                                           name=definition.name,
                                           sample_type=definition.type,
                                           unit=definition.unit,
                                           volume=value,
                                           res_metadata=metadata,
                                           extra=extra,
                                           name_prefix=None)
            samples.append(s)
        return samples

    @classmethod
    def build_pollsters(cls, conf):
        if not cls.mapping:
            definition_cfg = declarative.load_definitions(
                conf, {}, conf.hardware.meter_definitions_file,
                pkg_resources.resource_filename(__name__, "data/snmp.yaml"))
            cls.mapping = load_definition(definition_cfg)

        pollsters = []
        for name in cls.mapping:
            pollster = cls(conf)
            pollster._update_meter_definition(cls.mapping[name])
            pollsters.append((name, pollster))
        return pollsters


def load_definition(config_def):
    mappings = {}
    for meter_def in config_def.get('metric', []):
        try:
            meter = MeterDefinition(meter_def)
            mappings[meter.name] = meter
        except declarative.DefinitionException as e:
            errmsg = "Error loading meter definition: %s"
            LOG.error(errmsg, e.brief_message)
    return mappings
