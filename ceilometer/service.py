# Copyright 2012-2014 eNovance <licensing@enovance.com>
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

import socket
import sys

from keystoneauth1 import loading as ka_loading
from oslo_config import cfg
import oslo_i18n
from oslo_log import log
from oslo_policy import opts as policy_opts
from oslo_reports import guru_meditation_report as gmr

from ceilometer.conf import defaults
from ceilometer import keystone_client
from ceilometer import messaging
from ceilometer import sample
from ceilometer import version

OPTS = [
    cfg.StrOpt('host',
               default=socket.gethostname(),
               sample_default='<your_hostname>',
               help='Name of this node, which must be valid in an AMQP '
               'key. Can be an opaque identifier. For ZeroMQ only, must '
               'be a valid host name, FQDN, or IP address.'),
    cfg.IntOpt('http_timeout',
               default=600,
               help='Timeout seconds for HTTP requests. Set it to None to '
                    'disable timeout.'),
]
cfg.CONF.register_opts(OPTS)

NOTI_OPT = cfg.IntOpt('workers',
                      default=1,
                      min=1,
                      deprecated_group='DEFAULT',
                      deprecated_name='notification_workers',
                      help='Number of workers for notification service, '
                           'default value is 1.')
cfg.CONF.register_opt(NOTI_OPT, 'notification')

COLL_OPT = cfg.IntOpt('workers',
                      default=1,
                      min=1,
                      deprecated_group='DEFAULT',
                      deprecated_name='collector_workers',
                      help='Number of workers for collector service. '
                           'default value is 1.')
cfg.CONF.register_opt(COLL_OPT, 'collector')

keystone_client.register_keystoneauth_opts(cfg.CONF)


def prepare_service(argv=None, config_files=None, conf=None):
    if argv is None:
        argv = sys.argv

    # FIXME(sileht): Use ConfigOpts() instead
    if conf is None:
        conf = cfg.CONF

    oslo_i18n.enable_lazy()
    log.register_options(conf)
    log_levels = (conf.default_log_levels +
                  ['futurist=INFO', 'neutronclient=INFO',
                   'keystoneclient=INFO'])
    log.set_defaults(default_log_levels=log_levels)
    defaults.set_cors_middleware_defaults()
    policy_opts.set_defaults(conf)

    conf(argv[1:], project='ceilometer', validate_default_values=True,
         version=version.version_info.version_string(),
         default_config_files=config_files)

    ka_loading.load_auth_from_conf_options(conf, "service_credentials")

    log.setup(conf, 'ceilometer')
    sample.setup(conf)

    # NOTE(liusheng): guru cannot run with service under apache daemon, so when
    # ceilometer-api running with mod_wsgi, the argv is [], we don't start
    # guru.
    if argv:
        gmr.TextGuruMeditation.setup_autorun(version)
    messaging.setup()
    return conf
