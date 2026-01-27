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

from ceilometer.polling import plugin_base
from ceilometer import sample

LOG = log.getLogger(__name__)

# Manila share status values mapped to numeric values
SHARE_STATUS = {
    'available': 1,
    'creating': 2,
    'deleting': 3,
    'error': 4,
    'error_deleting': 5,
    'migrating': 6,
    'extending': 7,
    'shrinking': 8,
    'reverting': 9,
    'inactive': 10,
    'manage_starting': 11,
    'manage_error': 12,
    'unmanage_starting': 13,
    'unmanage_error': 14,
    'unmanaged': 15,
    'extending_error': 16,
    'shrinking_error': 17,
    'reverting_error': 18,
    'awaiting_transfer': 19,
    'backup_creating': 20,
    'backup_restoring': 21,
    'backup_restoring_error': 22,
    'creating_from_snapshot': 23,
    'shrinking_possible_data_loss_error': 24,
    'migrating_to': 25,
    'replication_change': 26,
}


class _BaseSharePollster(plugin_base.PollsterBase):
    """Base pollster for Manila share metrics."""

    # Fields to extract from openstacksdk Share objects
    # Note: share_protocol is renamed to 'protocol' in metadata for
    # compatibility with gnocchi_resources.yaml
    FIELDS = ['name',
              'availability_zone',
              'share_protocol',
              'share_type',
              'share_network_id',
              'status',
              'host',
              'is_public',
              ]

    @property
    def default_discovery(self):
        return 'manila_shares'

    @staticmethod
    def extract_metadata(share):
        metadata = {k: getattr(share, k, None)
                    for k in _BaseSharePollster.FIELDS}
        # Rename share_protocol to protocol for gnocchi_resources.yaml
        # compatibility with existing manila_share resource type
        if 'share_protocol' in metadata:
            metadata['protocol'] = metadata.pop('share_protocol')
        return metadata


class ShareStatusPollster(_BaseSharePollster):
    """Pollster for Manila share status."""

    @staticmethod
    def get_status_id(value):
        if not value:
            return -1
        status = value.lower()
        return SHARE_STATUS.get(status, -1)

    def get_samples(self, manager, cache, resources):
        for share in resources or []:
            LOG.debug("Processing share: %s", share.id)
            status = self.get_status_id(share.status)
            if status == -1:
                LOG.warning(
                    "Unknown status %(status)s for share "
                    "%(name)s (%(id)s), setting status to -1",
                    {"status": share.status,
                     "name": share.name,
                     "id": share.id})
            yield sample.Sample(
                name='manila.share.status',
                type=sample.TYPE_GAUGE,
                unit='status',
                volume=status,
                user_id=getattr(share, 'user_id', None),
                project_id=share.project_id,
                resource_id=share.id,
                resource_metadata=self.extract_metadata(share)
            )


class ShareSizePollster(_BaseSharePollster):
    """Pollster for Manila share size."""

    def get_samples(self, manager, cache, resources):
        for share in resources or []:
            LOG.debug("Processing share: %s", share.id)
            size = share.size if share.size is not None else 0
            yield sample.Sample(
                name='manila.share.size',
                type=sample.TYPE_GAUGE,
                unit='GiB',
                volume=size,
                user_id=getattr(share, 'user_id', None),
                project_id=share.project_id,
                resource_id=share.id,
                resource_metadata=self.extract_metadata(share)
            )
