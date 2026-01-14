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

from oslo_log import log

from ceilometer import designate_client
from ceilometer.polling import plugin_base
from ceilometer import sample

LOG = log.getLogger(__name__)

# Designate zone status values mapped to numeric values
ZONE_STATUS = {
    'active': 1,
    'pending': 2,
    'error': 3,
    'deleted': 4,
}

# Designate zone action values mapped to numeric values
ZONE_ACTION = {
    'none': 0,
    'create': 1,
    'delete': 2,
    'update': 3,
}


class _BaseZonePollster(plugin_base.PollsterBase):
    """Base pollster for Designate DNS zone metrics."""

    FIELDS = ['name',
              'email',
              'ttl',
              'description',
              'type',
              'status',
              'action',
              'serial',
              'pool_id',
              ]

    @property
    def default_discovery(self):
        return 'dns_zones'

    @staticmethod
    def extract_metadata(zone):
        return {k: getattr(zone, k, None)
                for k in _BaseZonePollster.FIELDS}


class ZoneStatusPollster(_BaseZonePollster):
    """Pollster for Designate DNS zone status."""

    @staticmethod
    def get_status_id(value):
        if not value:
            return -1
        status = value.lower()
        return ZONE_STATUS.get(status, -1)

    def get_samples(self, manager, cache, resources):
        for zone in resources or []:
            LOG.debug("DNS ZONE: %s", zone)
            status = self.get_status_id(zone.status)
            if status == -1:
                LOG.warning(
                    "Unknown status %(status)s for DNS zone "
                    "%(name)s (%(id)s), setting volume to -1",
                    {"status": zone.status,
                     "name": zone.name,
                     "id": zone.id})
            yield sample.Sample(
                name='dns.zone.status',
                type=sample.TYPE_GAUGE,
                unit='status',
                volume=status,
                user_id=None,
                project_id=zone.project_id,
                resource_id=zone.id,
                resource_metadata=self.extract_metadata(zone)
            )


class ZoneRecordsetCountPollster(_BaseZonePollster):
    """Pollster for Designate DNS zone recordset count."""

    def __init__(self, conf):
        super().__init__(conf)
        self.designate_cli = designate_client.Client(conf)

    def get_samples(self, manager, cache, resources):
        for zone in resources or []:
            LOG.debug("DNS ZONE: %s", zone)
            recordsets = list(self.designate_cli.recordsets_list(zone))
            count = len(recordsets)
            yield sample.Sample(
                name='dns.zone.recordsets',
                type=sample.TYPE_GAUGE,
                unit='recordset',
                volume=count,
                user_id=None,
                project_id=zone.project_id,
                resource_id=zone.id,
                resource_metadata=self.extract_metadata(zone)
            )


class ZoneTTLPollster(_BaseZonePollster):
    """Pollster for Designate DNS zone TTL."""

    def get_samples(self, manager, cache, resources):
        for zone in resources or []:
            LOG.debug("DNS ZONE: %s", zone)
            ttl = zone.ttl if zone.ttl is not None else 0
            yield sample.Sample(
                name='dns.zone.ttl',
                type=sample.TYPE_GAUGE,
                unit='second',
                volume=ttl,
                user_id=None,
                project_id=zone.project_id,
                resource_id=zone.id,
                resource_metadata=self.extract_metadata(zone)
            )


class ZoneSerialPollster(_BaseZonePollster):
    """Pollster for Designate DNS zone serial number."""

    def get_samples(self, manager, cache, resources):
        for zone in resources or []:
            LOG.debug("DNS ZONE: %s", zone)
            serial = zone.serial if zone.serial is not None else 0
            yield sample.Sample(
                name='dns.zone.serial',
                type=sample.TYPE_GAUGE,
                unit='serial',
                volume=serial,
                user_id=None,
                project_id=zone.project_id,
                resource_id=zone.id,
                resource_metadata=self.extract_metadata(zone)
            )
