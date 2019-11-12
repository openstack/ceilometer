#
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

""" All monasca ceilometer config opts"""

from oslo_config import cfg

OPTS = [

    # from monasca_client
    cfg.StrOpt('clientapi_version',
               default='2_0',
               help='Version of Monasca client to use while publishing.'),
    cfg.BoolOpt('enable_api_pagination',
                default=False,
                help='Enable paging through monasca api resultset.'),

    # from monasca_data_filter
    cfg.StrOpt('monasca_mappings',
               default='/etc/ceilometer/monasca_field_definitions.yaml',
               help='Monasca static and dynamic field mappings'),

    # from multi region opts
    cfg.StrOpt('control_plane',
               default='None',
               help='The name of control plane'),
    cfg.StrOpt('cluster',
               default='None',
               help='The name of cluster'),
    cfg.StrOpt('cloud_name',
               default='None',
               help='The name of cloud'),

    # from publisher monasca
    cfg.BoolOpt('batch_mode',
                default=True,
                help='Indicates whether samples are'
                     ' published in a batch.'),
    cfg.IntOpt('batch_count',
               default=1000,
               help='Maximum number of samples in a batch.'),
    cfg.IntOpt('batch_timeout',
               default=15,
               help='Maximum time interval(seconds) after which '
                    'samples are published in a batch.'),
    cfg.IntOpt('batch_polling_interval',
               default=5,
               help='Frequency of checking if batch criteria is met.'),
    cfg.BoolOpt('retry_on_failure',
                default=False,
                help='Indicates whether publisher retries publishing '
                     'sample in case of failure. Only a few error cases '
                     'are queued for a retry.'),
    # NOTE: the retry interval is hard coded for the periodicals decorator
    cfg.IntOpt('batch_max_retries',
               default=3,
               help='Maximum number of retry attempts on a publishing '
                    'failure to Monasca API.'),
    cfg.BoolOpt('archive_on_failure',
                default=False,
                help='When turned on, archives metrics in file system when '
                     'publish to Monasca fails or metric publish maxes out '
                     'retry attempts.'),
    cfg.StrOpt('archive_path',
               default='mon_pub_failures.txt',
               help='File of metrics that failed to publish to '
                    'Monasca. These include metrics that failed to '
                    'publish on first attempt and failed metrics that'
                    ' maxed out their retries.'),
    # For use with the monasca_client
    cfg.IntOpt('client_max_retries',
               default=3,
               help='Maximum number of retry attempts of connecting to '
                    'Monasca API.'),
    cfg.IntOpt('client_retry_interval',
               default=60,
               help='Frequency of attempting a retry connecting to Monasca '
                    'API.'),

]
