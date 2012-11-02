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

from ceilometer.openstack.common import cfg
from nova.openstack.common import importutils


db_driver_opt = cfg.StrOpt('db_driver',
                           default='nova.db',
                           help='driver to use for database access')


cfg.CONF.register_opt(db_driver_opt)


# FIXME(dhellmann): How do we get a list of instances without
# talking directly to the database?
class Resources(object):

    def __init__(self):
        self.db = importutils.import_module(cfg.CONF.db_driver)

    def instance_get_all_by_host(self, context):
        return self.db.instance_get_all_by_host(context, cfg.CONF.host)

    def floating_ip_get_all(self, context):
        return self.db.floating_ip_get_all(context)
