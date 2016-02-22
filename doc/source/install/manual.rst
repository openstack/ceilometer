..
      Copyright 2012 Nicolas Barcet for Canonical
                2013 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _installing_manually:

=====================
 Installing Manually
=====================


Storage Backend Installation
============================

This step is a prerequisite for the collector, notification agent and API
services. You may use one of the listed database backends below to store
Ceilometer data.

.. note::
   Please notice, MongoDB requires pymongo_ to be installed on the system. The
   required minimum version of pymongo is 2.4.
..


MongoDB
-------

   The recommended Ceilometer storage backend is `MongoDB`. Follow the
   instructions to install the MongoDB_ package for your operating system, then
   start the service. The required minimum version of MongoDB is 2.4.

   To use MongoDB as the storage backend, change the 'database' section in
   ceilometer.conf as follows::

    [database]
    connection = mongodb://username:password@host:27017/ceilometer

SQLalchemy-supported DBs
------------------------

   You may alternatively use `MySQL` (or any other SQLAlchemy-supported DB
   like `PostgreSQL`).

   In case of SQL-based database backends, you need to create a `ceilometer`
   database first and then initialise it by running::

    ceilometer-dbsync

   To use MySQL as the storage backend, change the 'database' section in
   ceilometer.conf as follows::

    [database]
    connection = mysql+pymysql://username:password@host/ceilometer?charset=utf8

HBase
-----

   HBase backend is implemented to use HBase Thrift interface, therefore it is
   mandatory to have the HBase Thrift server installed and running. To start
   the Thrift server, please run the following command::

    ${HBASE_HOME}/bin/hbase thrift start

   The implementation uses `HappyBase`_, which is a wrapper library used to
   interact with HBase via Thrift protocol. You can verify the thrift
   connection by running a quick test from a client::

    import happybase

    conn = happybase.Connection(host=$hbase-thrift-server,
                                port=9090,
                                table_prefix=None,
                                table_prefix_separator='_')
    print conn.tables() # this returns a list of HBase tables in your HBase server

   .. note::
      HappyBase version 0.5 or greater is required. Additionally, version 0.7
      is not currently supported.
   ..

   In case of HBase, the needed database tables (`project`, `user`, `resource`,
   `meter`) should be created manually with `f` column family for each one.

   To use HBase as the storage backend, change the 'database' section in
   ceilometer.conf as follows::

    [database]
    connection = hbase://hbase-thrift-host:9090

   It is possible to customize happybase's `table_prefix` and `table_prefix_separator`
   via query string. By default `table_prefix` is not set and `table_prefix_separator`
   is '_'. When `table_prefix` is not specified `table_prefix_separator` is not taken
   into account. E.g. the resource table in the default case will be 'resource' while
   with `table_prefix` set to 'ceilo' and `table_prefix_separator` to '.' the resulting
   table will be 'ceilo.resource'. For this second case this is the database connection
   configuration::

    [database]
    connection = hbase://hbase-thrift-host:9090?table_prefix=ceilo&table_prefix_separator=.

.. _HappyBase: http://happybase.readthedocs.org/en/latest/index.html#
.. _MongoDB: http://www.mongodb.org/
.. _pymongo: https://pypi.python.org/pypi/pymongo/



Installing the notification agent
======================================
.. index::
   double: installing; agent-notification

1. If you want to be able to retrieve image samples, you need to instruct
   Glance to send notifications to the bus by changing ``notifier_strategy``
   to ``rabbit`` in ``glance-api.conf`` and restarting the
   service.

2. If you want to be able to retrieve volume samples, you need to instruct
   Cinder to send notifications to the bus by changing ``notification_driver``
   to ``messagingv2`` and ``control_exchange`` to ``cinder``, before restarting
   the service.

3. If you want to be able to retrieve instance samples, you need to instruct
   Nova to send notifications to the bus by setting these values::

      # nova-compute configuration for ceilometer
      instance_usage_audit=True
      instance_usage_audit_period=hour
      notify_on_state_change=vm_and_task_state
      notification_driver=messagingv2

4. In order to retrieve object store statistics, ceilometer needs
   access to swift with ``ResellerAdmin`` role. You should give this
   role to your ``os_username`` user for tenant ``os_tenant_name``:

   ::

     $ keystone role-create --name=ResellerAdmin
     +----------+----------------------------------+
     | Property |              Value               |
     +----------+----------------------------------+
     |    id    | 462fa46c13fd4798a95a3bfbe27b5e54 |
     |   name   |          ResellerAdmin           |
     +----------+----------------------------------+

     $ keystone user-role-add --tenant_id $SERVICE_TENANT \
                              --user_id $CEILOMETER_USER \
                              --role_id 462fa46c13fd4798a95a3bfbe27b5e54

   You'll also need to add the Ceilometer middleware to Swift to account for
   incoming and outgoing traffic, by adding these lines to
   ``/etc/swift/proxy-server.conf``::

     [filter:ceilometer]
     use = egg:ceilometer#swift

   And adding ``ceilometer`` in the ``pipeline`` of that same file, right
   before ``proxy-server``.

   Additionally, if you want to store extra metadata from headers, you need
   to set ``metadata_headers`` so it would look like::

     [filter:ceilometer]
     use = egg:ceilometer#swift
     metadata_headers = X-FOO, X-BAR

   .. note::

        Please make sure that ceilometer's logging directory (if it's configured)
        is read and write accessible for the user swift is started by.

5. Clone the ceilometer git repository to the management server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

6. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

7. Copy the sample configuration files from the source tree
   to their final location.

   ::

      $ mkdir -p /etc/ceilometer
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

8. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure messaging

      Set the messaging related options correctly so ceilometer's daemons can
      communicate with each other and receive notifications from the other
      projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit
         for now.

   2. Set the ``telemetry_secret`` value.

      Set the ``telemetry_secret`` value to a large, random, value. Use
      the same value in all ceilometer configuration files, on all
      nodes, so that messages passing between the nodes can be
      validated.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

9. Start the notification daemon.

   ::

     $ ceilometer-agent-notification

   .. note::

      The default development configuration of the collector logs to
      stderr, so you may want to run this step using a screen session
      or other tool for maintaining a long-running program in the
      background.


Installing the collector
========================

.. index::
   double: installing; collector

.. _storage_backends:

1. Clone the ceilometer git repository to the management server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

2. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

3. Copy the sample configuration files from the source tree
   to their final location.

   ::

      $ mkdir -p /etc/ceilometer
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure messaging

      Set the messaging related options correctly so ceilometer's daemons can
      communicate with each other and receive notifications from the other
      projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit
         for now.

   2. Set the ``telemetry_secret`` value.

      Set the ``telemetry_secret`` value to a large, random, value. Use
      the same value in all ceilometer configuration files, on all
      nodes, so that messages passing between the nodes can be
      validated.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

5. Start the collector.

   ::

     $ ceilometer-collector

   .. note::

      The default development configuration of the collector logs to
      stderr, so you may want to run this step using a screen session
      or other tool for maintaining a long-running program in the
      background.

Installing the Polling Agent
============================

.. index::
   double: installing; agent

.. note::

   The polling agent needs to be able to talk to Keystone and any of
   the services being polled for updates. It also needs to run on your compute
   nodes to poll instances.

1. Clone the ceilometer git repository to the server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

2. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

3. Copy the sample configuration files from the source tree
   to their final location.

   ::

      $ mkdir -p /etc/ceilometer
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Edit ``/etc/ceilometer/ceilometer.conf``
   Set the messaging related options correctly so ceilometer's daemons can
   communicate with each other and receive notifications from the other
   projects.

   In particular, look for the ``*_control_exchange`` options and
   make sure the names are correct. If you did not change the
   ``control_exchange`` settings for the other components, the
   defaults should be correct.

   .. note::

      Ceilometer makes extensive use of the messaging bus, but has
      not yet been tested with ZeroMQ. We recommend using Rabbit
      for now.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

5. Start the agent

   ::

    $ ceilometer-polling

6. By default, the polling agent polls the `compute` and `central` namespaces.
   You can specify which namespace to poll in the `ceilometer.conf`
   configuration file or on the command line::

     $ ceilometer-polling --polling-namespaces central,ipmi


Installing the API Server
=========================

.. index::
   double: installing; API

.. note::
   The API server needs to be able to talk to keystone and ceilometer's
   database.

1. Clone the ceilometer git repository to the server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

2. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

3. Copy the sample configuration files from the source tree
   to their final location.

   ::

      $ mkdir -p /etc/ceilometer
      $ cp etc/ceilometer/api_paste.ini /etc/ceilometer
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure messaging

      Set the messaging related options correctly so ceilometer's daemons can
      communicate with each other and receive notifications from the other
      projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit
         for now.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

5. (Optional) As of the Juno release, Ceilometer utilises Paste Deploy to
   manage WSGI applications. Ceilometer uses keystonemiddleware by default but
   additional middleware and applications can be configured in api_paste.ini.
   For examples on how to use Paste Deploy, refer to this documentation_.

.. _documentation: http://pythonpaste.org/deploy/

6. Choose and start the API server.

   Ceilometer includes the ``ceilometer-api`` command. This can be
   used to run the API server. For smaller or proof-of-concept
   installations this is a reasonable choice. For larger installations it
   is strongly recommended to install the API server in a WSGI host
   such as mod_wsgi (see :doc:`mod_wsgi`). Doing so will provide better
   performance and more options for making adjustments specific to the
   installation environment.

   If you are using the ``ceilometer-api`` command it can be started
   as::

    $ ceilometer-api

.. note::

   The development version of the API server logs to stderr, so you
   may want to run this step using a screen session or other tool for
   maintaining a long-running program in the background.


Configuring keystone to work with API
=====================================

.. index::
   double: installing; configure keystone

.. note::
   The API server needs to be able to talk to keystone to authenticate.

1. Create a service for ceilometer in keystone

   ::

      $ keystone service-create --name=ceilometer \
                                --type=metering \
                                --description="Ceilometer Service"

2. Create an endpoint in keystone for ceilometer

   ::

      $ keystone endpoint-create --region RegionOne \
                                 --service_id $CEILOMETER_SERVICE \
                                 --publicurl "http://$SERVICE_HOST:8777/" \
                                 --adminurl "http://$SERVICE_HOST:8777/" \
                                 --internalurl "http://$SERVICE_HOST:8777/"

.. note::

   CEILOMETER_SERVICE is the id of the service created by the first command
   and SERVICE_HOST is the host where the Ceilometer API is running. The
   default port value for ceilometer API is 8777. If the port value
   has been customized, adjust accordingly.


Configuring Heat to send notifications
======================================

Configure the driver in ``heat.conf``

   ::

        notification_driver=messagingv2


Configuring Sahara to send notifications
========================================

Configure the driver in ``sahara.conf``

   ::

        enable_notifications=true
        notification_driver=messagingv2

Also you need to configure messaging related options correctly as written above
for other parts of installation guide. Refer to :doc:`/configuration` for
details about any other options you might want to modify before starting the
service.


Configuring MagnetoDB to send notifications
===========================================

Configure the driver in ``magnetodb-async-task-executor.conf``

   ::

        notification_driver=messagingv2

You also would need to restart the service magnetodb-async-task-executor
(if it's already running) after changing the above configuration file.


Notifications queues
========================

.. index::
   double: installing; notifications queues; multiple topics

By default, Ceilometer consumes notifications on the messaging bus sent to
**notification_topics** by using a queue/pool name that is identical to the
topic name. You shouldn't have different applications consuming messages from
this queue. If you want to also consume the topic notifications with a system
other than Ceilometer, you should configure a separate queue that listens for
the same messages.

Ceilometer allows multiple topics to be configured so that polling agent can
send the same messages of notifications to other queues. Notification agents
also use **notification_topics** to configure which queue to listen for. If
you use multiple topics, you should configure notification agent and polling
agent separately, otherwise Ceilometer collects duplicate samples.

By default, the ceilometer.conf file is as follows::

   [DEFAULT]
   notification_topics = notifications

To use multiple topics, you should give ceilometer-agent-notification and
ceilometer-polling services different ceilometer.conf files. The Ceilometer
configuration file ceilometer.conf is normally locate in the /etc/ceilometer
directory. Make changes according to your requirements which may look like
the following::

For notification agent using ceilometer-notification.conf, settings like::

   [DEFAULT]
   notification_topics = notifications,xxx

For polling agent using ceilometer-polling.conf, settings like::

   [DEFAULT]
   notification_topics = notifications,foo

.. note::

   notification_topics in ceilometer-notification.conf should only have one same
   topic in ceilometer-polling.conf

Doing this, it's easy to listen/receive data from multiple internal and external services.


Using multiple dispatchers
================================

.. index::
   double: installing; multiple dispatchers

The Ceilometer collector allows multiple dispatchers to be configured so that
data can be easily sent to multiple internal and external systems. Dispatchers
are divided between ``event_dispatchers`` and ``meter_dispatchers`` which can
each be provided with their own set of receiving systems.

.. note::
   In Liberty and prior the configuration option for all data was
   ``dispatcher`` but this was changed for the Mitaka release to break out
   separate destination systems by type of data.

By default, Ceilometer only saves event and meter data in a database. If you
want Ceilometer to send data to other systems, instead of or in addition to
the Ceilometer database, multiple dispatchers can be enabled by modifying the
Ceilometer configuration file.

Ceilometer ships multiple dispatchers currently. They are ``database``,
``file``, ``http`` and ``gnocchi`` dispatcher. As the names imply, database
dispatcher sends metering data to a database, file dispatcher logs meters into
a file, http dispatcher posts the meters onto a http target, gnocchi
dispatcher posts the meters onto Gnocchi_ backend. Each dispatcher can have
its own configuration parameters. Please see available configuration
parameters at the beginning of each dispatcher file.

.. _Gnocchi: http://gnocchi.readthedocs.org/en/latest/basic.html

To check if any of the dispatchers is available in your system, you can
inspect the Ceilometer egg entry_points.txt file, you should normally see text
like the following::

   [ceilometer.dispatcher]
   database = ceilometer.dispatcher.database:DatabaseDispatcher
   file = ceilometer.dispatcher.file:FileDispatcher
   http = ceilometer.dispatcher.http:HttpDispatcher
   gnocchi = ceilometer.dispatcher.gnocchi:GnocchiDispatcher

To configure one or multiple dispatchers for Ceilometer, find the Ceilometer
configuration file ceilometer.conf which is normally located at /etc/ceilometer
directory and make changes accordingly. Your configuration file can be in a
different directory.

To use multiple dispatchers on a Ceilometer collector service, add multiple
dispatcher lines in ceilometer.conf file like the following::

   [DEFAULT]
   meter_dispatchers=database
   meter_dispatchers=file

If there is no dispatcher present, database dispatcher is used as the
default. If in some cases such as traffic tests, no dispatcher is needed,
one can configure the line without a dispatcher, like the following::

   event_dispatchers=

With the above configuration, no event dispatcher is used by the Ceilometer
collector service, all event data received by Ceilometer collector will be
dropped.

For Gnocchi dispatcher, the following configuration settings should be added::

    [DEFAULT]
    meter_dispatchers = gnocchi

    [dispatcher_gnocchi]
    archive_policy = low

The value specified for ``archive_policy`` should correspond to the name of an
``archive_policy`` configured within Gnocchi.

For Gnocchi dispatcher backed by Swift storage, the following additional
configuration settings should be added::

    [dispatcher_gnocchi]
    filter_project = gnocchi_swift
    filter_service_activity = True

.. note::
   If gnocchi dispatcher is enabled, Ceilometer api calls will return a 410 with
   an empty result. The Gnocchi Api should be used instead to access the data.
