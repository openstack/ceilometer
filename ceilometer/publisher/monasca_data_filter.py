#
# Copyright 2015 Hewlett-Packard Company
# (c) Copyright 2018 SUSE LLC
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

import datetime

from jsonpath_rw_ext import parser
from oslo_log import log
from oslo_utils import timeutils
import six
import yaml

from ceilometer import sample as sample_util

LOG = log.getLogger(__name__)


class UnableToLoadMappings(Exception):
    pass


class NoMappingsFound(Exception):
    pass


class CeiloscaMappingDefinitionException(Exception):
    def __init__(self, message, definition_cfg):
        super(CeiloscaMappingDefinitionException, self).__init__(message)
        self.message = message
        self.definition_cfg = definition_cfg

    def __str__(self):
        return '%s %s: %s' % (self.__class__.__name__,
                              self.definition_cfg, self.message)


class MonascaDataFilter(object):
    JSONPATH_RW_PARSER = parser.ExtentedJsonPathParser()

    def __init__(self, conf):
        self.conf = conf
        self._mapping = {}
        self._mapping = self._get_mapping()

    def _get_mapping(self):
        with open(self.conf.monasca.monasca_mappings, 'r') as f:
            try:
                return yaml.safe_load(f)
            except yaml.YAMLError as err:
                if hasattr(err, 'problem_mark'):
                    mark = err.problem_mark
                    errmsg = ("Invalid YAML syntax in Monasca Data "
                              "Filter file %(file)s at line: "
                              "%(line)s, column: %(column)s."
                              % dict(file=self.conf.monasca.monasca_mappings,
                                     line=mark.line + 1,
                                     column=mark.column + 1))
                else:
                    errmsg = ("YAML error reading Monasca Data Filter "
                              "file %(file)s" %
                              dict(file=self.conf.monasca.monasca_mappings))
                LOG.error(errmsg)
                raise UnableToLoadMappings(err.message)

    def _convert_timestamp(self, timestamp):
        if isinstance(timestamp, datetime.datetime):
            ts = timestamp
        else:
            ts = timeutils.parse_isotime(timestamp)
        tdelta = (ts - datetime.datetime(1970, 1, 1, tzinfo=ts.tzinfo))
        # convert timestamp to milli seconds as Monasca expects
        return int(tdelta.total_seconds() * 1000)

    def _convert_to_sample(self, s):
        return sample_util.Sample(
            name=s['counter_name'],
            type=s['counter_type'],
            unit=s['counter_unit'],
            volume=s['counter_volume'],
            user_id=s['user_id'],
            project_id=s['project_id'],
            resource_id=s['resource_id'],
            timestamp=s['timestamp'],
            resource_metadata=s['resource_metadata'],
            source=s.get('source')).as_dict()

    def get_value_for_nested_dictionary(self, lst, dct):
        val = dct
        for element in lst:
            if isinstance(val, dict) and element in val:
                val = val.get(element)
            else:
                return
        return val

    def parse_jsonpath(self, field):
        try:
            parts = self.JSONPATH_RW_PARSER.parse(field)
        except Exception as e:
            raise CeiloscaMappingDefinitionException(
                "Parse error in JSONPath specification "
                "'%(jsonpath)s': %(err)s"
                % dict(jsonpath=field, err=e))
        return parts

    def _get_value_metadata_for_key(self, sample_meta, meta_key):
        """Get the data for the given key, supporting JSONPath"""
        if isinstance(meta_key, dict):
            # extract key and jsonpath
            # If following convention, dict will have one and only one
            # element of the form <monasca key>: <json path>
            if len(meta_key.keys()) == 1:
                mon_key = list(meta_key.keys())[0]
            else:
                # If no keys or more keys than one
                raise CeiloscaMappingDefinitionException(
                    "Field definition format mismatch, should "
                    "have only one key:value pair. %(meta_key)s" %
                    {'meta_key': meta_key}, meta_key)
            json_path = meta_key[mon_key]
            parts = self.parse_jsonpath(json_path)
            val_matches = parts.find(sample_meta)
            if len(val_matches) > 0:
                # resolve the find to the first match and get value
                val = val_matches[0].value
                if not isinstance(val, (str, six.text_type)) \
                   and not isinstance(val, int):
                    # Don't support lists or dicts or ...
                    raise CeiloscaMappingDefinitionException(
                        "Metadata format mismatch, value "
                        "should be a simple string. %(valuev)s" %
                        {'valuev': val}, meta_key)
            else:
                val = 'None'
            return mon_key, val
        else:
            # simple string
            val = sample_meta.get(meta_key, None)
            if val is not None:
                return meta_key, val
            else:
                # one more attempt using a dotted notation
                # TODO(joadavis) Deprecate this . notation code
                # in favor of jsonpath
                if len(meta_key.split('.')) > 1:
                    val = self.get_value_for_nested_dictionary(
                        meta_key.split('.'), sample_meta)
                    if val is not None:
                        return meta_key, val
                    else:
                        return meta_key, 'None'
                else:
                    return meta_key, 'None'

    def process_sample_for_monasca(self, sample_obj):
        if not self._mapping:
            raise NoMappingsFound("Unable to process the sample")

        dimensions = {}
        dimensions['datasource'] = 'ceilometer'
        # control_plane, cluster and cloud_name can be None, but we use
        # literal 'None' for such case
        dimensions['control_plane'] = self.conf.monasca.control_plane or 'None'
        dimensions['cluster'] = self.conf.monasca.cluster or 'None'
        dimensions['cloud_name'] = self.conf.monasca.cloud_name or 'None'
        if isinstance(sample_obj, sample_util.Sample):
            sample = sample_obj.as_dict()
        elif isinstance(sample_obj, dict):
            if 'counter_name' in sample_obj:
                sample = self._convert_to_sample(sample_obj)
            else:
                sample = sample_obj

        for dim in self._mapping['dimensions']:
            val = sample.get(dim, None)
            if val:
                dimensions[dim] = val
            else:
                dimensions[dim] = 'None'

        sample_meta = sample.get('resource_metadata', None)
        value_meta = {}

        meter_name = sample.get('name') or sample.get('counter_name')
        if sample_meta:
            for meta_key in self._mapping['metadata']['common']:
                monasca_key, val = self._get_value_metadata_for_key(
                    sample_meta, meta_key)
                value_meta[monasca_key] = val

            if meter_name in self._mapping['metadata'].keys():
                for meta_key in self._mapping['metadata'][meter_name]:
                    monasca_key, val = self._get_value_metadata_for_key(
                        sample_meta, meta_key)
                    value_meta[monasca_key] = val

        meter_value = sample.get('volume') or sample.get('counter_volume')
        if meter_value is None:
            meter_value = 0

        metric = dict(
            name=meter_name,
            timestamp=self._convert_timestamp(sample['timestamp']),
            value=meter_value,
            dimensions=dimensions,
            value_meta=value_meta,
        )

        LOG.debug("Generated metric with name %(name)s,"
                  " timestamp %(timestamp)s, value %(value)s,"
                  " dimensions %(dimensions)s" %
                  {'name': metric['name'],
                   'timestamp': metric['timestamp'],
                   'value': metric['value'],
                   'dimensions': metric['dimensions']})

        return metric
