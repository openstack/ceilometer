# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Copyright 2013 IBM Corp
# All Rights Reserved.
#
# Author: Julien Danjou <julien@danjou.info>
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

from ceilometer.central import plugin
from ceilometer import nova_client
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import sample


class FloatingIPPollster(plugin.CentralPollster):

    LOG = log.getLogger(__name__ + '.floatingip')

    def _get_floating_ips(self):
        nv = nova_client.Client()
        return nv.floating_ip_get_all()

    def _iter_floating_ips(self, cache):
        if 'floating_ips' not in cache:
            cache['floating_ips'] = list(self._get_floating_ips())
        return iter(cache['floating_ips'])

    def get_samples(self, manager, cache, resources=[]):
        for ip in self._iter_floating_ips(cache):
            self.LOG.info(_("FLOATING IP USAGE: %s") % ip.ip)
            # FIXME (flwang) Now Nova API /os-floating-ips can't provide those
            # attributes were used by Ceilometer, such as project id, host.
            # In this fix, those attributes usage will be removed temporarily.
            # And they will be back after fix the Nova bug 1174802.
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
