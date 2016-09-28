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

This step is a prerequisite for the collector and API services. You may use
one of the listed database backends below to store Ceilometer data.

Gnocchi
-------

1. Follow `Gnocchi installation`_ instructions

2. Initialize Gnocchi for Ceilometer::

    $ gnocchi-upgrade --create-legacy-resource-types

   .. note::

      Prior to Gnocchi 2.1, Ceilometer resource types were included, therefore
      --create-legacy-resource-types flag is not needed.

3. Edit `/etc/ceilometer/ceilometer.conf` for the collector service::

     [DEFAULT]
     meter_dispatchers = gnocchi
     event_dispatchers = gnocchi

     [dispatcher_gnocchi]
     filter_service_activity = False # Enable if using swift backend
     filter_project = <project name associated with gnocchi user> # if using swift backend

     [service_credentials]
     auth_url = <auth_url>:5000
     region_name = RegionOne
     password = password
     username = ceilometer
     project_name = service
     project_domain_id = default
     user_domain_id = default
     auth_type = password

4. Copy gnocchi_resources.yaml to config directory (e.g./etc/ceilometer)

5. To minimize data requests, caching and batch processing should be enabled:

   1. Enable resource caching (oslo.cache_ should be installed)::

        [cache]
        backend_argument = redis_expiration_time:600
        backend_argument = db:0
        backend_argument = distributed_lock:True
        backend_argument = url:redis://localhost:6379
        backend = dogpile.cache.redis

   2. Enable batch processing::

        [collector]
        batch_size = 100
        batch_timeout = 5

6. Start collector service

.. _oslo.cache: http://docs.openstack.org/developer/oslo.cache/opts.html


MongoDB
-------

   Follow the instructions to install the MongoDB_ package for your operating
   system, then start the service. The required minimum version of MongoDB is
   2.4.x. You will also need to have pymongo_ 2.4 installed

   To use MongoDB as the storage backend, change the 'database' section in
   ceilometer.conf as follows::

    [database]
    connection = mongodb://username:password@host:27017/ceilometer

SQLalchemy-supported DBs
------------------------

   You may alternatively use any SQLAlchemy-supported DB such as
   `PostgreSQL` or `MySQL`.

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
   interact with HBase via Thrift protocol. You can verify the Thrift
   connection by running a quick test from a client:

   .. code-block:: python

    import happybase

    conn = happybase.Connection(host=$hbase-thrift-server,
                                port=9090,
                                table_prefix=None,
                                table_prefix_separator='_')
    print conn.tables() # this returns a list of HBase tables in your HBase server

   .. note::

      HappyBase version 0.5 or greater is required. Additionally, version 0.7
      is not currently supported.

   In the case of HBase, the required database tables (`project`, `user`, `resource`,
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

   To ensure proper configuration, please add the following lines to the
   `hbase-site.xml` configuration file::

    <property>
      <name>hbase.thrift.minWorkerThreads</name>
      <value>200</value>
    </property>

.. _`Gnocchi installation`: http://docs.openstack.org/developer/gnocchi/install.html
.. _HappyBase: http://happybase.readthedocs.org/en/latest/index.html#
.. _MongoDB: http://www.mongodb.org/
.. _pymongo: https://pypi.python.org/pypi/pymongo/


Installing the notification agent
=================================

.. index::
   double: installing; agent-notification

1. Clone the ceilometer git repository to the management server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

2. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

3. Copy the sample configuration files from the source tree
   to their final location::

   $ mkdir -p /etc/ceilometer
   $ cp etc/ceilometer/*.json /etc/ceilometer
   $ cp etc/ceilometer/*.yaml /etc/ceilometer
   $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure messaging::

        [oslo_messaging_notifications]
        topics = notifications

        [oslo_messaging_rabbit]
        rabbit_userid = stackrabbit
        rabbit_password = openstack1
        rabbit_hosts = 10.0.2.15

   2. Set the ``telemetry_secret`` value.

      Set the ``telemetry_secret`` value to a large, random, value. Use
      the same value in all ceilometer configuration files, on all
      nodes, so that messages passing between the nodes can be
      validated. This value can be left empty to disable message signing.

      .. note::

         Disabling signing will improve message handling performance

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

5. Start the notification daemon::

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
   to their final location::

   $ mkdir -p /etc/ceilometer
   $ cp etc/ceilometer/*.json /etc/ceilometer
   $ cp etc/ceilometer/*.yaml /etc/ceilometer
   $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure messaging::

        [oslo_messaging_notifications]
        topics = notifications

        [oslo_messaging_rabbit]
        rabbit_userid = stackrabbit
        rabbit_password = openstack1
        rabbit_hosts = 10.0.2.15

   2. Set the ``telemetry_secret`` value (if enabled for notification agent)

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

5. Start the collector::

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
   to their final location::

   $ mkdir -p /etc/ceilometer
   $ cp etc/ceilometer/*.json /etc/ceilometer
   $ cp etc/ceilometer/*.yaml /etc/ceilometer
   $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Configure messaging by editing ``/etc/ceilometer/ceilometer.conf``::

     [oslo_messaging_notifications]
     topics = notifications

     [oslo_messaging_rabbit]
     rabbit_userid = stackrabbit
     rabbit_password = openstack1
     rabbit_hosts = 10.0.2.15

5. In order to retrieve object store statistics, ceilometer needs
   access to swift with ``ResellerAdmin`` role. You should give this
   role to your ``os_username`` user for tenant ``os_tenant_name``::

     $ openstack role create ResellerAdmin
     +-----------+----------------------------------+
     | Field     | Value                            |
     +-----------+----------------------------------+
     | domain_id | None                             |
     | id        | f5153dae801244e8bb4948f0a6fb73b7 |
     | name      | ResellerAdmin                    |
     +-----------+----------------------------------+

     $ openstack role add f5153dae801244e8bb4948f0a6fb73b7 \
                          --project $SERVICE_TENANT \
                          --user $CEILOMETER_USER

6. Start the agent::

   $ ceilometer-polling

7. By default, the polling agent polls the `compute` and `central` namespaces.
   You can specify which namespace to poll in the `ceilometer.conf`
   configuration file or on the command line::

     $ ceilometer-polling --polling-namespaces central,ipmi


Installing the API Server
=========================

.. index::
   double: installing; API

.. note::

   The API server needs to be able to talk to keystone and ceilometer's
   database. It is only required if you choose to store data in legacy
   database or if you inject new samples via REST API.

1. Clone the ceilometer git repository to the server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

2. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

3. Copy the sample configuration files from the source tree
   to their final location::

   $ mkdir -p /etc/ceilometer
   $ cp etc/ceilometer/api_paste.ini /etc/ceilometer
   $ cp etc/ceilometer/*.json /etc/ceilometer
   $ cp etc/ceilometer/*.yaml /etc/ceilometer
   $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Configure messaging by editing ``/etc/ceilometer/ceilometer.conf``::

     [oslo_messaging_notifications]
     topics = notifications

     [oslo_messaging_rabbit]
     rabbit_userid = stackrabbit
     rabbit_password = openstack1
     rabbit_hosts = 10.0.2.15

5. Create a service for ceilometer in keystone::

     $ openstack service create metering --name=ceilometer \
                                         --description="Ceilometer Service"

6. Create an endpoint in keystone for ceilometer::

     $ openstack endpoint create $CEILOMETER_SERVICE \
                                 --region RegionOne \
                                 --publicurl "http://$SERVICE_HOST:8777" \
                                 --adminurl "http://$SERVICE_HOST:8777" \
                                 --internalurl "http://$SERVICE_HOST:8777"

   .. note::

     CEILOMETER_SERVICE is the id of the service created by the first command
     and SERVICE_HOST is the host where the Ceilometer API is running. The
     default port value for ceilometer API is 8777. If the port value
     has been customized, adjust accordingly.

7. Choose and start the API server.

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


Enabling Service Notifications
==============================

Cinder
------

Edit ``cinder.conf`` to include::

  [oslo_messaging_notifications]
  driver = messagingv2

Glance
------

Edit ``glance.conf`` to include::

  [oslo_messaging_notifications]
  driver = messagingv2

Heat
----

Configure the driver in ``heat.conf``::

  [oslo_messaging_notifications]
  driver=messagingv2

Neutron
------

Edit ``neutron.conf`` to include::

  [oslo_messaging_notifications]
  driver = messagingv2

Nova
----

Edit ``nova.conf`` to include::

  [DEFAULT]
  instance_usage_audit=True
  instance_usage_audit_period=hour
  notify_on_state_change=vm_and_task_state

  [oslo_messaging_notifications]
  driver=messagingv2


Sahara
------

Configure the driver in ``sahara.conf``::

  [DEFAULT]
  enable_notifications=true

  [oslo_messaging_notifications]
  driver=messagingv2


Swift
-----

Edit ``proxy-server.conf`` to include::

  [filter:ceilometer]
  topic = notifications
  driver = messaging
  url = rabbit://stackrabbit:openstack1@10.0.2.15:5672/
  control_exchange = swift
  paste.filter_factory = ceilometermiddleware.swift:filter_factory
  set log_level = WARN

and edit [pipeline:main] to include the ceilometer middleware before the application::

  [pipeline:main]
  pipeline = catch_errors ... ... ceilometer proxy-server


Also, you need to configure messaging related options correctly as written above
for other parts of installation guide. Refer to :doc:`/configuration` for
details about any other options you might want to modify before starting the
service.
