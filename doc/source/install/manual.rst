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

        [notification]
        batch_size = 100
        batch_timeout = 5

6. Start notification service

.. _oslo.cache: http://docs.openstack.org/developer/oslo.cache/opts.html
.. _`Gnocchi installation`: http://docs.openstack.org/developer/gnocchi/install.html


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

3. Generate configuration file::

   $ tox -egenconfig

4. Copy the sample configuration files from the source tree
   to their final location::

   $ mkdir -p /etc/ceilometer
   $ cp etc/ceilometer/*.yaml /etc/ceilometer
   $ cp etc/ceilometer/ceilometer.conf /etc/ceilometer

5. Edit ``/etc/ceilometer/ceilometer.conf``

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

6. Edit ``/etc/ceilometer/ceilometer.conf``:

   Change publisher endpoints to expected targets. By default, it pushes to a
   `metering.sample` topic on the oslo.messaging queue. Available publishers
   are listed in :ref:`pipeline-publishers` section.

5. Start the notification daemon::

     $ ceilometer-agent-notification

   .. note::

      The default development configuration of the notification logs to
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

3. Generate configuration file::

   $ tox -egenconfig

4. Copy the sample configuration files from the source tree
   to their final location::

   $ mkdir -p /etc/ceilometer
   $ cp etc/ceilometer/*.yaml /etc/ceilometer
   $ cp etc/ceilometer/ceilometer.conf /etc/ceilometer/ceilometer.conf

5. Configure messaging by editing ``/etc/ceilometer/ceilometer.conf``::

     [oslo_messaging_rabbit]
     rabbit_userid = stackrabbit
     rabbit_password = openstack1
     rabbit_hosts = 10.0.2.15

6. In order to retrieve object store statistics, ceilometer needs
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

7. Start the agent::

   $ ceilometer-polling

8. By default, the polling agent polls the `compute` and `central` namespaces.
   You can specify which namespace to poll in the `ceilometer.conf`
   configuration file or on the command line::

     $ ceilometer-polling --polling-namespaces central,ipmi


Installing the API Server
=========================

.. index::
   double: installing; API

.. note::

   The Ceilometer's API service is no longer supported. Data storage should be
   handled by a separate service such as Gnocchi.


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
