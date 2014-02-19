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

Installing the notification agent
======================================
.. index::
   double: installing; agent-notification

1. If you want to be able to retrieve image samples, you need to instruct
   Glance to send notifications to the bus by changing ``notifier_strategy``
   to ``rabbit`` or ``qpid`` in ``glance-api.conf`` and restarting the
   service.

2. If you want to be able to retrieve volume samples, you need to instruct
   Cinder to send notifications to the bus by changing ``notification_driver``
   to ``cinder.openstack.common.notifier.rpc_notifier`` and
   ``control_exchange`` to ``cinder``, before restarting the service.

3. In order to retrieve object store statistics, ceilometer needs
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

4. Clone the ceilometer git repository to the management server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

5. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

6. Copy the sample configuration files from the source tree
   to their final location.

   ::

      $ mkdir -p /etc/ceilometer
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

7. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure RPC

      Set the RPC-related options correctly so ceilometer's daemons
      can communicate with each other and receive notifications from
      the other projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit or
         qpid for now.

   2. Set the ``metering_secret`` value.

      Set the ``metering_secret`` value to a large, random, value. Use
      the same value in all ceilometer configuration files, on all
      nodes, so that messages passing between the nodes can be
      validated.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

8. Start the notification daemon.

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

1. Install MongoDB.

   Follow the instructions to install the MongoDB_ package for your
   operating system, then start the service.

2. Clone the ceilometer git repository to the management server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

3. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

4. Copy the sample configuration files from the source tree
   to their final location.

   ::

      $ mkdir -p /etc/ceilometer
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

5. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure RPC

      Set the RPC-related options correctly so ceilometer's daemons
      can communicate with each other and receive notifications from
      the other projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit or
         qpid for now.

   2. Set the ``metering_secret`` value.

      Set the ``metering_secret`` value to a large, random, value. Use
      the same value in all ceilometer configuration files, on all
      nodes, so that messages passing between the nodes can be
      validated.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

6. Start the collector.

   ::

     $ ceilometer-collector

   .. note::

      The default development configuration of the collector logs to
      stderr, so you may want to run this step using a screen session
      or other tool for maintaining a long-running program in the
      background.

.. _MongoDB: http://www.mongodb.org/


Installing the Compute Agent
============================

.. index::
   double: installing; compute agent

.. note:: The compute agent must be installed on each nova compute node.

1. Configure nova.

   The ``nova`` compute service needs the following configuration to
   be set in ``nova.conf``::

      # nova-compute configuration for ceilometer
      instance_usage_audit=True
      instance_usage_audit_period=hour
      notify_on_state_change=vm_and_task_state
      notification_driver=nova.openstack.common.notifier.rpc_notifier
      notification_driver=ceilometer.compute.nova_notifier

2. Clone the ceilometer git repository to the server::

   $ cd /opt/stack
   $ git clone https://git.openstack.org/openstack/ceilometer.git

3. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

4. Copy the sample configuration files from the source tree
   to their final location.

   ::

      $ mkdir -p /etc/ceilometer
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

5. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure RPC

      Set the RPC-related options correctly so ceilometer's daemons
      can communicate with each other and receive notifications from
      the other projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit or
         qpid for now.

   2. Set the ``metering_secret`` value.

      Set the ``metering_secret`` value to a large, random, value. Use
      the same value in all ceilometer configuration files, on all
      nodes, so that messages passing between the nodes can be
      validated.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

6. Start the agent.

   ::

     $ ceilometer-agent-compute

   .. note::

      The default development configuration of the agent logs to
      stderr, so you may want to run this step using a screen session
      or other tool for maintaining a long-running program in the
      background.

Installing the Central Agent
============================

.. index::
   double: installing; agent

.. note::

   The central agent needs to be able to talk to keystone and any of
   the services being polled for updates.

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

   1. Configure RPC

      Set the RPC-related options correctly so ceilometer's daemons
      can communicate with each other and receive notifications from
      the other projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit or
         qpid for now.

   2. Set the ``metering_secret`` value.

      Set the ``metering_secret`` value to a large, random, value. Use
      the same value in all ceilometer configuration files, on all
      nodes, so that messages passing between the nodes can be
      validated.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

5. Start the agent

   ::

    $ ceilometer-agent-central


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
      $ cp etc/ceilometer/*.json /etc/ceilometer
      $ cp etc/ceilometer/*.yaml /etc/ceilometer
      $ cp etc/ceilometer/ceilometer.conf.sample /etc/ceilometer/ceilometer.conf

4. Edit ``/etc/ceilometer/ceilometer.conf``

   1. Configure RPC

      Set the RPC-related options correctly so ceilometer's daemons
      can communicate with each other and receive notifications from
      the other projects.

      In particular, look for the ``*_control_exchange`` options and
      make sure the names are correct. If you did not change the
      ``control_exchange`` settings for the other components, the
      defaults should be correct.

      .. note::

         Ceilometer makes extensive use of the messaging bus, but has
         not yet been tested with ZeroMQ. We recommend using Rabbit or
         qpid for now.

   Refer to :doc:`/configuration` for details about any other options
   you might want to modify before starting the service.

5. Start the API server.

   ::

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

        notification_driver=heat.openstack.common.notifier.rpc_notifier

Or if migration to oslo.messaging is done for Icehouse:

   ::

        notification_driver=oslo.messaging.notifier.Notifier


Notifications queues
========================

.. index::
   double: installing; notifications queues

By default, Ceilometer consumes notifications on the RPC bus sent to
**notification_topics** by using a queue/pool name that is identical to the
topic name. You shouldn't have different applications consuming messages
from this queue.
If you want to also consume the topic notifications with a system other than
Ceilometer, you should configure a separate queue that listens for the same
messages.

Using multiple dispatchers
================================

.. index::
   double: installing; multiple dispatchers

The Ceilometer collector allows multiple dispatchers to be configured so that
metering data can be easily sent to multiple internal and external systems.

Ceilometer by default only saves metering data in a database, to allow
Ceilometer to send metering data to other systems in addition to the
database, multiple dispatchers can be developed and enabled by modifying
Ceilometer configuration file.

Ceilometer ships two dispatchers currently. One is called database
dispatcher, and the other is called file dispatcher. As the names imply,
database dispatcher basically sends metering data to a database driver,
eventually metering data will be saved in database. File dispatcher sends
metering data into a file. The location, name, size of the file can be
configured in ceilometer configuration file. These two dispatchers are
shipped in the Ceilometer egg and defined in the entry_points as follows::

   [ceilometer.dispatcher]
   file = ceilometer.dispatcher.file:FileDispatcher
   database = ceilometer.dispatcher.database:DatabaseDispatcher

To use both dispatchers on a Ceilometer collector service, add the following
line in file ceilometer.conf::

   [DEFAULT]
   dispatcher=database
   dispatcher=file

.. note::

    dispatcher is in [collector] section in Havana release, but it is
    deprecated in Icehouse.

If there is no dispatcher present, database dispatcher is used as the
default. If in some cases such as traffic tests, no dispatcher is needed,
one can configure the line like the following::

   dispatcher=

With above configuration, no dispatcher is used by the Ceilometer collector
service, all metering data received by Ceilometer collector will be dropped.


Using other databases
=========================
.. index::
   double: installing; database, hbase, mysql, db2

Ceilometer by default uses mongodb as its backend data repository.
A deployment can choose to use other databases, currently the supported
databases are mongodb, hbase, mysql (or sqlalchemy-enabled databases) and
db2. To use a database other than MongoDB, edit the database section in
ceilometer.conf:

To use db2 as the data repository, make the section look like this::

   [database]
   connection = db2://username:password@host:27017/ceilometer

To use mongodb as the data repository, make the section look like this::

   [database]
   connection = mongodb://username:password@host:27017/ceilometer
