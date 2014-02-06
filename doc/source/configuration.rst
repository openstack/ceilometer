..
      Copyright 2012 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=======================
 Configuration Options
=======================

Ceilometer specific
===================

The following table lists the ceilometer specific options in the global configuration file.
Please note that ceilometer uses openstack-common extensively, which requires that
the other parameters are set appropriately. For information we are listing the configuration
elements that we use after the ceilometer specific elements.

If you use sql alchemy, its specific parameters will need to be set.


===============================  ====================================  ==============================================================
Parameter                        Default                               Note
===============================  ====================================  ==============================================================
nova_control_exchange            nova                                  Exchange name for Nova notifications
glance_control_exchange          glance                                Exchange name for Glance notifications
cinder_control_exchange          cinder                                Exchange name for Cinder notifications
neutron_control_exchange         neutron                               Exchange name for Neutron notifications
metering_secret                  change this or be hacked              Secret value for signing metering messages
metering_topic                   metering                              the topic ceilometer uses for metering messages
sample_source                    openstack                             The source name of emitted samples
control_exchange                 ceilometer                            AMQP exchange to connect to if using RabbitMQ or Qpid
database_connection              mongodb://localhost:27017/ceilometer  Database connection string
metering_api_port                8777                                  The port for the ceilometer API server
reseller_prefix                  AUTH\_                                Prefix used by swift for reseller token
===============================  ====================================  ==============================================================

Service polling authentication
==============================

The following options must be placed under a [service_credentials] section
and will be used by Ceilometer to retrieve information from OpenStack
components.

===============================  ====================================  ==============================================================
Parameter                        Default                               Note
===============================  ====================================  ==============================================================
os_username                      ceilometer                            Username to use for openstack service access
os_password                      admin                                 Password to use for openstack service access
os_tenant_id                                                           Tenant ID to use for openstack service access
os_tenant_name                   admin                                 Tenant name to use for openstack service access
os_auth_url                      http://localhost:5000/v2.0            Auth URL to use for openstack service access
os_endpoint_type                 publicURL                             Endpoint type in the catalog to use to access services
===============================  ====================================  ==============================================================

Keystone Middleware Authentication
==================================

The following table lists the Keystone middleware authentication options which are used to get admin token.
Please note that these options need to be under [keystone_authtoken] section.

===============================  ====================================  ==============================================================
Parameter                        Default                               Note
===============================  ====================================  ==============================================================
auth_host                                                              The host providing the Keystone service API endpoint for
                                                                       validating and requesting tokens
auth_port                        35357                                 The port used to validate tokens
auth_protocol                    https                                 The protocol used to validate tokens
auth_uri                         auth_protocol://auth_host:auth_port   The full URI used to validate tokens
admin_token                                                            Either this or the following three options are required. If
                                                                       set, this is a single shared secret with the Keystone
                                                                       configuration used to validate tokens.
admin_user                                                             User name for retrieving admin token
admin_password                                                         Password for retrieving admin token
admin_tenant_name                                                      Tenant name for retrieving admin token
signing_dir                                                            The cache directory for signing certificate
certfile                                                               Required if Keystone server requires client cert
keyfile                                                                Required if Keystone server requires client cert. This can be
                                                                       the same as certfile if the certfile includes the private key.
===============================  ====================================  ==============================================================

SQL Alchemy
===========

==========================  ====================================  ==============================================================
Parameter                   Default                               Note
==========================  ====================================  ==============================================================
sql_connection_debug        0                                     Verbosity of SQL debugging information. 0=None, 100=Everything
sql_connection_trace        False                                 Add python stack traces to SQL as comment strings
sql_idle_timeout            3600                                  timeout before idle sql connections are reaped
sql_max_retries             10                                    maximum db connection retries during startup.
                                                                  (setting -1 implies an infinite retry count)
sql_retry_interval          10                                    interval between retries of opening a sql connection
mysql_engine                InnoDB                                MySQL engine to use
sqlite_synchronous          True                                  If passed, use synchronous mode for sqlite
==========================  ====================================  ==============================================================

HBase
===================

To configure HBase as your database backend:

1. To install an HBase server, for pure development purpose, you can just
download the HBase image from Cloudera and get it up and running. Then the
quickest way to check it is to run the ``HBase shell`` and try a ``list``
command which would return the list of the tables in your HBase server:

 ::

    $ ${HBASE_HOME}/bin/hbase shell

    hbase> list

.. note::
    This driver has been tested against HBase 0.92.1/CDH 4.1.1,
    HBase 0.94.2/CDH 4.2.0, HBase 0.94.4/HDP 1.2 and HBase 0.94.5/Apache.
    Versions earlier than 0.92.1 are not supported due to feature incompatibility.

2. A few HBase tables are expected by Ceilometer.
To create them, run the following:

 ::

    $ ${HBASE_HOME}/bin/hbase shell

    hbase> create 'project', {NAME=>'f'}
    hbase> create 'user', {NAME=>'f'}
    hbase> create 'resource', {NAME=>'f'}
    hbase> create 'meter', {NAME=>'f'}

3. This driver is implemented to use HBase Thrift interface so it's necessary
to have the HBase Thrift server installed and started. When you have HBase
installed, normally, HBase thrift server is turned on by default. If it's not,
turn it on by running command ``hbase thrift start``. The implementation uses
`HappyBase`_ which is a wrapper library used to interact with HBase via Thrift
protocol, you can verify the thrift connection by running a quick test from a
client:

 .. _HappyBase: http://happybase.readthedocs.org/en/latest/index.html#

::

    import happybase

    conn = happybase.Connection(host=$hbase-thrift-server, port=9090, table_prefix=None)
    print conn.tables() # this returns a list of HBase tables in your HBase server

4. The parameter "database_connection" needs to be configured to point to
the Hbase Thrift server.

===========================  ====================================  ==============================================================
Parameter                    Value                                 Note
===========================  ====================================  ==============================================================
database_connection          hbase://$hbase-thrift-server:9090     Database connection string
===========================  ====================================  ==============================================================

.. note::

    If you are changing the configuration on the fly, you will need to restart
    the Ceilometer services that use the database to allow the changes to take
    affect, i.e. the collector and API services.

Event Conversion
================

The following options in the [event] configuration section affect the extraction of Event data from notifications.

==================================  ======================================  ==============================================================
Parameter                           Default                                 Note
==================================  ======================================  ==============================================================
drop_unmatched_notifications        False                                   If set to True, then notifications with no matching event
                                                                            definition will be dropped.
                                                                            (Notifications will *only* be dropped if this is True)
definitions_cfg_file                event_definitions.yaml                  Name of event definitions config file (yaml format)
==================================  ======================================  ==============================================================



General options
===============

The following is the list of openstack-common options that we use:

===========================  ====================================  ==============================================================
Parameter                    Default                               Note
===========================  ====================================  ==============================================================
default_notification_level   INFO                                  Default notification level for outgoing notifications
default_publisher_id         $host                                 Default publisher_id for outgoing notifications
bind_host                    0.0.0.0                               IP address to listen on
bind_port                    9292                                  Port numver to listen on
port                         5672                                  Rabbit MQ port to liste on
fake_rabbit                  False                                 If passed, use a fake RabbitMQ provider
publish_errors               False                                 publish error events
use_stderr                   True                                  Log output to standard error
logfile_mode                 0644                                  Default file mode used when creating log files
log_dir                                                            Log output to a per-service log file in named directory
log_file                                                           Log output to a named file
log_format                   date-time level name msg              Log format
log_date_format              YYYY-MM-DD hh:mm:ss                   Log date format
log_config                                                         Logging configuration file used. The options specified in that
                                                                    config file will override any other logging options specified
                                                                    in Ceilometer config file.
default_log_levels           ['amqplib=WARN',sqlalchemy=WARN,...]  Default log level per components
notification_topics          ['notifications', ]                   AMQP topic used for openstack notifications
enabled_apis                 ['ec2', 'osapi_compute']              List of APIs to enable by default
verbose                      False                                 Print more verbose output
debug                        False                                 Print debugging output
state_path                   currentdir                            Top-level directory for maintaining nova state
sqlite_db                    nova.sqlite                           file name for sqlite
sql_connection               sqlite:///$state_path/$sqlite_db      connection string for sql database
matchmaker_ringfile          /etc/nova/matchmaker_ring.json        Matchmaker ring file (JSON)
rpc_zmq_bind_address         '*'                                   ZeroMQ bind address
rpc_zmq_matchmaker           ceilometer.openstack.common.rpc.      MatchMaker drivers
                             matchmaker.MatchMakerLocalhost
rpc_zmq_port                 9501                                  ZeroMQ receiver listening port
rpc_zmq_port_pub             9502                                  ZeroMQ fanout publisher port
rpc_zmq_contexts             1                                     Number of ZeroMQ contexts
rpc_zmq_ipc_dir              /var/run/openstack                    Directory for holding IPC sockets
rabbit_port                  5672                                  The RabbitMQ broker port where a single node is used
rabbit_host                  localhost                             The RabbitMQ broker address where a single node is used
rabbit_hosts                 ['$rabbit_host:$rabbit_port']         The list of rabbit hosts to listen to
rabbit_userid                guest                                 the RabbitMQ userid
rabbit_password              guest                                 the RabbitMQ password
rabbit_virtual_host          /                                     the RabbitMQ virtual host
rabbit_retry_interval        1                                     how frequently to retry connecting with RabbitMQ
rabbit_retry_backoff         2                                     how long to backoff for between retries when connecting
rabbit_max_retries           0                                     maximum retries with trying to connect to RabbitMQ
                                                                   (the default of 0 implies an infinite retry count)
rabbit_durable_queues        False                                 use durable queues in RabbitMQ
rabbit_use_ssl               False                                 connect over SSL for RabbitMQ
rabbit_durable_queues        False                                 use durable queues in RabbitMQ
rabbit_ha_queues             False                                 use H/A queues in RabbitMQ (x-ha-policy: all).
kombu_ssl_version                                                  SSL version to use (valid only if SSL enabled)
kombu_ssl_keyfile                                                  SSL key file (valid only if SSL enabled)
kombu_ssl_certfile                                                 SSL cert file (valid only if SSL enabled)
kombu_ssl_ca_certs                                                 SSL certification authority file
qpid_hostname                localhost                             Qpid broker hostname
qpid_port                    5672                                  Qpid broker port
qpid_username                                                      Username for qpid connection
qpid_password                                                      Password for qpid connection
qpid_sasl_mechanisms                                               Space separated list of SASL mechanisms to use for auth
qpid_reconnect_timeout       0                                     Reconnection timeout in seconds
qpid_reconnect_limit         0                                     Max reconnections before giving up
qpid_reconnect_interval_min  0                                     Minimum seconds between reconnection attempts
qpid_reconnect_interval_max  0                                     Maximum seconds between reconnection attempts
qpid_reconnect_interval      0                                     Equivalent to setting max and min to the same value
qpid_heartbeat               60                                    Seconds between connection keepalive heartbeats
qpid_protocol                tcp                                   Transport to use, either 'tcp' or 'ssl'
qpid_reconnect               True                                  Automatically reconnect
qpid_tcp_nodelay             True                                  Disable Nagle algorithm
rpc_backend                  kombu                                 The messaging module to use, defaults to kombu.
rpc_thread_pool_size         64                                    Size of RPC thread pool
rpc_conn_pool_size           30                                    Size of RPC connection pool
rpc_response_timeout         60                                    Seconds to wait for a response from call or multicall
rpc_cast_timeout             30                                    Seconds to wait before a cast expires (TTL).
                                                                   Only supported by impl_zmq.
dispatchers                  database                              The list of dispatchers to process metering data.
===========================  ====================================  ==============================================================

A sample configuration file can be found in `ceilometer.conf.sample`_.

.. _ceilometer.conf.sample: https://git.openstack.org/cgit/openstack/ceilometer/tree/etc/ceilometer/ceilometer.conf.sample

Pipelines
=========

Pipelines describe chains of handlers, which can be transformers and/or
publishers.

The chain can start with a transformer, which is responsible for converting
the data, coming from the pollsters or notification handlers (for further
information see the :ref:`polling` section), to the required format, which
can mean dropping some parts of the sample, doing aggregation, changing
field or deriving samples for secondary meters, like in case of *cpu_util*,
see the example below, in the configuration details. The pipeline can contain
multiple transformers or none at all.

The chains end with one or more publishers. This component makes it possible
to persist the data into storage through the message bus or to send it to one
or more external consumers. One chain can contain multiple publishers, see the
:ref:`multi-publisher` section.

Pipeline configuration
----------------------

Pipeline configuration by default, is stored in a separate configuration file,
called pipeline.yaml, next to the ceilometer.conf file. The pipeline
configuration file can be set in the *pipeline_cfg_file* parameter in
ceilometer.conf. Multiple chains can be defined in one configuration file.

The chain definition looks like the following::

    ---
    -
    name: 'name of the pipeline'
    interval: 'how often should the samples be injected into the pipeline'
    meters:
        - 'meter filter'
    transformers: 'definition of transformers'
    publishers:
        - 'list of publishers'

The *interval* should be defined in seconds.

There are several ways to define the list of meters for a pipeline. The list
of valid meters can be found in the :ref:`measurements` section. There is
a possibility to define all the meters, or just included or excluded meters,
with which a pipeline should operate:

* To include all meters, use the '*' wildcard symbol.
* To define the list of meters, use either of the following:

  * To define the list of included meters, use the 'meter_name' syntax
  * To define the list of excluded meters, use the '!meter_name' syntax
  * For meters, which identify a complex Sample field, use the wildcard
    symbol to select all, e.g. for "instance:m1.tiny", use "instance:\*"

The above definition methods can be used in the following combinations:

* Only the wildcard symbol
* The list of included meters
* The list of excluded meters
* Wildcard symbol with the list of excluded meters

.. note::
    At least one of the above variations should be included in the meters
    section. Included and excluded meters cannot co-exist in the same
    pipeline. Wildcard and included meters cannot co-exist in the same
    pipeline definition section.

The *transformers* section provides the possibility to add a list of
transformer definitions. The names of the transformers should be the same
as the names of the related extensions in setup.cfg.

The definition of transformers can contain the following fields::

    transformers:
        - name: 'name of the transformer'
          parameters:

The *parameters* section can contain transformer specific fields, like source
and target fields with different subfields in case of the rate_of_change,
which depends on the implementation of the transformer. In case of the
transformer, which creates the *cpu_util* meter, the definition looks like the
following::

    transformers:
        - name: "rate_of_change"
          parameters:
              target:
                  name: "cpu_util"
                  unit: "%"
                  type: "gauge"
                  scale: "100.0 / (10**9 * (resource_metadata.cpu_number or 1))"

The *rate_of_change* transformer generates the *cpu_util* meter from the
sample values of the *cpu* counter, which represents cumulative CPU time in
nanoseconds. The transformer definition above defines a scale factor (for
nanoseconds, multiple CPUs, etc.), which is applied before the transformation
derives a sequence of gauge samples with unit '%', from the original values
of the *cpu* meter.

The definition for the disk I/O rate, which is also generated by the
*rate_of_change* transformer::

    transformers:
        - name: "rate_of_change"
          parameters:
              source:
                  map_from:
                      name: "disk\\.(read|write)\\.(bytes|requests)"
                      unit: "(B|request)"
              target:
                  map_to:
                      name: "disk.\\1.\\2.rate"
                      unit: "\\1/s"
                  type: "gauge"

The *publishers* section contains the list of publishers, where the samples
data should be sent after the possible transformations. The names of the
publishers should be the same as the related names of the plugins in
setup.cfg.

The default configuration can be found in `pipeline.yaml`_.

.. _pipeline.yaml: https://git.openstack.org/cgit/openstack/ceilometer/tree/etc/ceilometer/pipeline.yaml