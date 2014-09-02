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
api_paste_config                 api_paste.ini                         Configuration file for WSGI definition of the API
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
nova_http_log_debug              False                                 Log request/response parameters between nova and ceilometer
glance_page_size                 0                                     Number of items to request in each paginated Glance API
                                                                       request (parameter used by glancecelient). If this is less
                                                                       than or equal to 0, page size is not specified (default value
                                                                       in glanceclient is used). It is better to check and set
                                                                       appropriate value in line with each environment when calling
                                                                       glanceclient, than to define higher default value.
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

VMware Configuration Options
============================

The following lists the various options that the VMware driver supports and must be placed
under a section called '[vmware]'.

==========================  ====================================  =================================================================
Parameter                   Default                               Note
==========================  ====================================  =================================================================
host_ip                     ""                                    (Str) IP address of the VMware Vsphere host.
host_password               ""                                    (Str) Password of VMware Vsphere.
host_username               ""                                    (Str) Username of VMware Vsphere.
api_retry_count             10                                    (Int) Number of times a VMware Vsphere API must be retried.
task_poll_interval          0.5                                   (Float) Sleep time in seconds for polling an ongoing async task.
wsdl_location               None                                  (Str) Optional vim Service WSDL location
                                                                  e.g http://<server>/vimService.wsdl. Optional over-ride to
                                                                  default location for bug work-arounds.
==========================  ====================================  =================================================================

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

This storage implementation uses Thrift HBase interface. The default Thrift's
connection settings should be changed to support using ConnectionPool in HBase.
To ensure proper configuration, please add the following lines to the
`hbase-site.xml` configuration file::

    <property>
      <name>hbase.thrift.minWorkerThreads</name>
      <value>200</value>
    </property>

For pure development purposes, you can use HBase from Apache_ or some other
vendors like Cloudera or Hortonworks. To verify your installation, you can use
the `list` command in `HBase shell`, to list the tables in your
HBase server, as follows::

    $ ${HBASE_HOME}/bin/hbase shell

    hbase> list

.. note::
    This driver has been tested against HBase 0.94.2/CDH 4.2.0,
    HBase 0.94.4/HDP 1.2, HBase 0.94.18/Apache, HBase 0.94.5/Apache,
    HBase 0.96.2/Apache and HBase 0.98.0/Apache.
    Versions earlier than 0.92.1 are not supported due to feature incompatibility.

To find out more about supported storage backends please take a look on the
:doc:`install/manual/` guide.

.. note::

    If you are changing the configuration on the fly to use HBase, as a storage
    backend, you will need to restart the Ceilometer services that use the
    database to allow the changes to take affect, i.e. the collector and API
    services.

.. _Apache: https://hbase.apache.org/book/quickstart.html

Event Conversion
================

[notification] configuration section switches on events storing.

==================================  ======================================  ==============================================================
Parameter                           Default                                 Note
==================================  ======================================  ==============================================================
store_events                        False                                   Boolean variable that switch on/off events storing
==================================  ======================================  ==============================================================

The following options in the [event] configuration section affect the extraction of Event data from notifications.

==================================  ======================================  ==============================================================
Parameter                           Default                                 Note
==================================  ======================================  ==============================================================
drop_unmatched_notifications        False                                   If set to True, then notifications with no matching event
                                                                            definition will be dropped.
                                                                            (Notifications will *only* be dropped if this is True)
definitions_cfg_file                event_definitions.yaml                  Name of event definitions config file (yaml format)
==================================  ======================================  ==============================================================

Alarming
========

The following options in the [alarm] configuration section affect the configuration of alarm services

======================  ==============  ====================================================================================
Parameter               Default         Note
======================  ==============  ====================================================================================
evaluation_service      singleton       Driver to use for alarm evaluation service:
                                          * singleton:   All alarms are evaluated by one alarm evaluation service instance
                                          * partitioned: All alarms are dispatched across all alarm evaluation service
                                            instances to be evaluate
======================  ==============  ====================================================================================


Collector
=========

The following options in the [collector] configuration section affect the collector service

=====================================  ======================================  ==============================================================
Parameter                              Default                                 Note
=====================================  ======================================  ==============================================================
requeue_sample_on_dispatcher_error     False                                   Requeue the sample on the collector sample queue when the
                                                                               collector fails to dispatch it. This option is only valid if
                                                                               the sample comes from the notifier publisher
=====================================  ======================================  ==============================================================



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


Sample Configuration file
=========================

The sample configuration file for Ceilometer, named
etc/ceilometer/ceilometer.conf.sample, was removed from version control after
the Icehouse release. For more details, please read the file
etc/ceilometer/README-ceilometer.conf.txt. You can generate this sample
configuration file by running ``tox -e genconfig``.

.. note::
    tox version 1.7.0 and 1.7.1 have a `backward compatibility issue`_
    with OpenStack projects. If you meet the "tox.ConfigError: ConfigError:
    substitution key 'posargs' not found" problem, run
    ``sudo pip install -U "tox>=1.6.1,!=1.7.0,!=1.7.1"`` to get a proper
    version, then try ``tox -e genconfig`` again.

.. _`backward compatibility issue`: https://bitbucket.org/hpk42/tox/issue/150/posargs-configerror

.. _Pipeline-Configuration:

Pipelines
=========

Pipelines describe a coupling between sources of samples and the
corresponding sinks for transformation and publication of these
data.

A source is a producer of samples, in effect a set of pollsters and/or
notification handlers emitting samples for a set of matching meters.
See :doc:`contributing/plugins` and :ref:`plugins-and-containers` for
details on how to write and plug in your plugins.

Each source configuration encapsulates meter name matching, polling
interval determination, optional resource enumeration or discovery,
and mapping to one or more sinks for publication.

A sink on the other hand is a consumer of samples, providing logic for
the transformation and publication of samples emitted from related sources.
Each sink configuration is concerned `only` with the transformation rules
and publication conduits for samples.

In effect, a sink describes a chain of handlers. The chain starts with
zero or more transformers and ends with one or more publishers. The first
transformer in the chain is passed samples from the corresponding source,
takes some action such as deriving rate of change, performing unit conversion,
or aggregating, before passing the modified sample to next step.

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
    sources:
      - name: 'source name'
        interval: 'how often should the samples be injected into the pipeline'
        meters:
          - 'meter filter'
        resources:
          - 'list of resource URLs'
        sinks
          - 'sink name'
    sinks:
      - name: 'sink name'
        transformers: 'definition of transformers'
        publishers:
          - 'list of publishers'

The *name* parameter of a source is unrelated to anything else;
nothing references a source by name, and a source's name does not have
to match anything.

The *interval* parameter in the sources section should be defined in seconds. It
determines the cadence of sample injection into the pipeline, where samples are
produced under the direct control of an agent, i.e. via a polling cycle as opposed
to incoming notifications.

There are several ways to define the list of meters for a pipeline source. The
list of valid meters can be found in the :ref:`measurements` section. There is
a possibility to define all the meters, or just included or excluded meters,
with which a source should operate:

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

A given polling plugin is invoked according to each source section
whose *meters* parameter matches the plugin's meter name.  That is,
the matching source sections are combined by union, not intersection,
of the prescribed time series.

The optional *resources* section of a pipeline source allows a static
list of resource URLs to be to be configured. An amalgamated list of all
statically configured resources for a set of pipeline sources with a
common interval is passed to individual pollsters matching those pipelines.

The *transformers* section of a pipeline sink provides the possibility to add a
list of transformer definitions. The names of the transformers should be the same
as the names of the related extensions in setup.cfg. For a more detailed
description, please see the :ref:`transformers` section.

The *publishers* section contains the list of publishers, where the samples
data should be sent after the possible transformations. The names of the
publishers should be the same as the related names of the plugins in
setup.cfg.

The default configuration can be found in `pipeline.yaml`_.

.. _pipeline.yaml: https://git.openstack.org/cgit/openstack/ceilometer/tree/etc/ceilometer/pipeline.yaml

.. _publishers:

Publishers
++++++++++

The definition of publishers looks like::

    publishers:
        - udp://10.0.0.2:1234
        - rpc://?per_meter_topic=1
        - notifier://?policy=drop&max_queue_length=512

The udp publisher is configurable like this: *udp://<host>:<port>/*

The rpc publisher is configurable like this:
*rpc://?option1=value1&option2=value2*

Same thing for the notifier publisher:
*notifier://?option1=value1&option2=value2*

For rpc and notifier the options are:

- *per_meter_topic=1* to publish the samples on additional
  *<metering_topic>.<sample_name>* topic queue besides the *<metering_topic>*
  queue
- *policy=(default|drop|queue)* to configure the behavior when the publisher
  fails to send the samples, where the predefined values mean the following:

  - *default*, wait and block until the samples have been sent
  - *drop*, drop the samples which are failed to be sent
  - *queue*, create an in-memory queue and retry to send the samples on the
    queue on the next samples publishing (the queue length can be configured
    with *max_queue_length=1024*, 1024 is the default)

.. _transformers:

Transformers
************

The definition of transformers can contain the following fields::

    transformers:
        - name: 'name of the transformer'
          parameters:

The *parameters* section can contain transformer specific fields, like source
and target fields with different subfields in case of the rate_of_change,
which depends on the implementation of the transformer.

.. _rate_of_change_transformer:

Rate of change transformer
++++++++++++++++++++++++++

In the case of the transformer that creates the *cpu_util* meter, the definition
looks like the following::

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

Unit conversion transformer
+++++++++++++++++++++++++++

Transformer to apply a unit conversion. It takes the volume of the meter
and multiplies it with the given 'scale' expression. Also supports *map_from*
and *map_to* like the :ref:`rate_of_change_transformer`.

Sample configuration::

    transformers:
    - name: "unit_conversion"
      parameters:
          target:
              name: "disk.kilobytes"
              unit: "KB"
              scale: "1.0 / 1024.0"

With the *map_from* and *map_to*::

    transformers:
        - name: "unit_conversion"
          parameters:
              source:
                  map_from:
                      name: "disk\\.(read|write)\\.bytes"
              target:
                  map_to:
                      name: "disk.\\1.kilobytes"
                  scale: "1.0 / 1024.0"
                  unit: "KB"

Aggregator transformer
++++++++++++++++++++++

A transformer that sums up the incoming samples until enough samples have
come in or a timeout has been reached.

Timeout can be specified with the *retention_time* parameter. If we want to
flush the aggregation after a set number of samples have been aggregated,
we can specify the *size* parameter.

The volume of the created sample is the sum of the volumes of samples that
came into the transformer. Samples can be aggregated by the attributes
*project_id*, *user_id* and *resource_metadata*. To aggregate by the chosen
attributes, specify them in the configuration and set which value of the
attribute to take for the new sample (*first* to take the first sample's
attribute, *last* to take the last sample's attribute, and *drop* to discard
the attribute).

To aggregate 60s worth of samples by resource_metadata and keep the
resource_metadata of the latest received sample::

    transformers:
    - name: "aggregator"
      parameters:
          retention_time: 60
          resource_metadata: last

To aggregate each 15 samples by user_id and resource_metadata and keep the
user_id of the first received sample and drop the resource_metadata::

    transformers:
    - name: "aggregator"
      parameters:
          size: 15
          user_id: first
          resource_metadata: drop

Accumulator transformer
+++++++++++++++++++++++

This transformer simply caches the samples until enough samples have arrived
and then flushes them all down the pipeline at once.
::

    transformers:
    - name: "accumulator"
      parameters:
          size: 15

Multi meter arithmetic transformer
++++++++++++++++++++++++++++++++++

This transformer enables us to perform arithmetic calculations
over one or more meters and/or their metadata, for example:

    memory_util = 100 * memory.usage / memory .

A new sample is created with the properties described in the 'target'
section of the transformer's configuration. The sample's volume is the result
of the provided expression. The calculation is performed on samples from the
same resource.

.. note::
    The calculation is limited to meters with the same interval.

Example configuration::

    transformers:
    - name: "arithmetic"
      parameters:
        target:
          name: "memory_util"
          unit: "%"
          type: "gauge"
          expr: "100 * $(memory.usage) / $(memory)"

To demonstrate the use of metadata, here is the implementation of
a silly metric that shows average CPU time per core::

    transformers:
    - name: "arithmetic"
      parameters:
        target:
          name: "avg_cpu_per_core"
          unit: "ns"
          type: "cumulative"
          expr: "$(cpu) / ($(cpu).resource_metadata.cpu_number or 1)"

Expression evaluation gracefully handles NaNs and exceptions. In such
a case it does not create a new sample but only logs a warning.
