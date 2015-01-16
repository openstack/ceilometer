#
# Copyright 2012 eNovance <licensing@enovance.com>
#
# Copyright 2013 IBM Corp
# All Rights Reserved.
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

from oslo_config import cfg
from oslo_log import log
from oslo_utils import timeutils

from ceilometer.agent import plugin_base
from ceilometer.i18n import _
from ceilometer import nova_client
from ceilometer import sample


LOG = log.getLogger(__name__)


class FloatingIPPollster(plugin_base.PollsterBase):

    @staticmethod
    def _get_floating_ips(ksclient, endpoint):
        nv = nova_client.Client(
            auth_token=ksclient.auth_token, bypass_url=endpoint)
        return nv.floating_ip_get_all()

    def _iter_floating_ips(self, ksclient, cache, endpoint):
        key = '%s-floating_ips' % endpoint
        if key not in cache:
            cache[key] = list(self._get_floating_ips(ksclient, endpoint))
        return iter(cache[key])

    @property
    def default_discovery(self):
        return 'endpoint:%s' % cfg.CONF.service_types.nova

    def get_samples(self, manager, cache, resources):
        for endpoint in resources:
            for ip in self._iter_floating_ips(manager.keystone, cache,
                                              endpoint):
                LOG.info(_("FLOATING IP USAGE: %s") % ip.ip)
                # FIXME (flwang) Now Nova API /os-floating-ips can't provide
                # those attributes were used by Ceilometer, such as project
                # id, host. In this fix, those attributes usage will be
                # removed temporarily. And they will be back after fix the
                # Nova bug 1174802.
                yield sample.Sample(
                    name='ip.floating',
                    type=sample.TYPE_GAUGE,
                    unit='ip',
                    volume=1,
                    user_id=None,
                    project_id=None,
                    resource_id=ip.id,
                    timestamp=timeutils.utcnow().isoformat(),
                    resource_metadata={
                        'address': ip.ip,
                        'pool': ip.pool
                    })
