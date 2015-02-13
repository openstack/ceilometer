#
# Copyright 2015 eNovance <licensing@enovance.com>
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


from keystoneclient.v2_0 import client as ksclient
from oslo_config import cfg

cfg.CONF.import_group('service_credentials', 'ceilometer.service')
cfg.CONF.import_opt('http_timeout', 'ceilometer.service')


def get_client():
    return ksclient.Client(
        username=cfg.CONF.service_credentials.os_username,
        password=cfg.CONF.service_credentials.os_password,
        tenant_id=cfg.CONF.service_credentials.os_tenant_id,
        tenant_name=cfg.CONF.service_credentials.os_tenant_name,
        cacert=cfg.CONF.service_credentials.os_cacert,
        auth_url=cfg.CONF.service_credentials.os_auth_url,
        region_name=cfg.CONF.service_credentials.os_region_name,
        insecure=cfg.CONF.service_credentials.insecure,
        timeout=cfg.CONF.http_timeout,)
