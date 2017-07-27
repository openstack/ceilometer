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

.. note::

   Ceilometer collector service is deprecated. Configure dispatchers under publisher
   in pipeline to push data instead. For more details about how to configure
   publishers in the :ref:`publisher-configuration`.

Storage Backend Installation
============================


Gnocchi
-------

#. Follow `Gnocchi installation`_ instructions

#. Edit `/etc/ceilometer/ceilometer.conf` for the collector service:

   * With Keystone authentication enabled::

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

   * In somes cases, it is possible to disable keystone authentication for
     Gnocchi to remove the overhead of token creation/verification when request
     authentication doesn't matter. This will increase the performance of
     Gnocchi::

       [dispatcher_gnocchi]
       filter_service_activity = False # Enable if using swift backend
       filter_project = <project name associated with gnocchi user> # if using swift backend
       auth_section=service_credentials_gnocchi

       [service_credentials_gnocchi]
       auth_type=gnocchi-noauth
       roles = admin
       user_id = <ceilometer_user_id>
       project_id = <ceilometer_project_id>
       endpoint = <gnocchi_endpoint>

#. Copy gnocchi_resources.yaml to config directory (e.g./etc/ceilometer)

#. Initialize Gnocchi database by creating ceilometer resources::

   ceilometer-upgrade --skip-metering-database

#. To minimize data requests, caching and batch processing should be enabled:

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

#. Start notification service

.. _oslo.cache: https://docs.openstack.org/oslo.cache/latest/configuration/index.html
.. _`Gnocchi installation`: http://gnocchi.xyz/install.html


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
   $ cp etc/ceilometer/ceilometer.conf /etc/ceilometer
   $ cp ceilometer/pipeline/data/*.yaml /etc/ceilometer

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
   $ cp etc/ceilometer/ceilometer.conf /etc/ceilometer/ceilometer.conf
   $ cp ceilometer/pipeline/data/*.yaml /etc/ceilometer

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

See the `install guide`_ for instructions on how to enable meters for specific
OpenStack services.

.. _`install guide`: https://docs.openstack.org/project-install-guide/telemetry/draft/install-controller.html
