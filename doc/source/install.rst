..
      Copyright 2012 Nicolas Barcet for Canonical

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _install:

================================================
Install
================================================

Installing and Running the Development Version
++++++++++++++++++++++++++++++++++++++++++++++

Ceilometer has four daemons. The :term:`compute agent` runs on the
Nova compute node(s) while the :term:`central agent` and
:term:`collector` run on the cloud's management node(s). In a
development environment created by devstack_, these two are typically
the same server. They do not have to be, though, so some of the
instructions below are duplicated. Skip the steps you have already
done.

.. _devstack: http://www.devstack.org/

Configuring Devstack
====================

.. index::
   double: installing; devstack

1. Create a ``localrc`` file as input to devstack.

2. Ceilometer makes extensive use of the messaging bus, but has not
   yet been tested with ZeroMQ. We recommend using Rabbit or qpid for
   now.

3. Nova does not generate the periodic notifications for all known
   instances by default. To enable these auditing events, set
   ``instance_usage_audit`` to true in the nova configuration file.

4. The ceilometer services are not enabled by default, so they must be
   enabled in ``localrc`` before running ``stack.sh``.

This example ``localrc`` file shows all of the settings required for
ceilometer::

   # Enable the ceilometer services
   enable_service ceilometer-acompute,ceilometer-acentral,ceilometer-collector,ceilometer-api


Installing Manually
+++++++++++++++++++

Installing the Collector
========================

.. index::
   double: installing; collector

1. Install and configure nova.

   The collector daemon imports code from ``nova``, so it needs to be
   run on a server where nova has already been installed.

   .. note::

      Ceilometer makes extensive use of the messaging bus, but has not
      yet been tested with ZeroMQ. We recommend using Rabbit or qpid
      for now.

2. If you want to be able to retrieve image counters, you need to instruct
   Glance to send notifications to the bus by changing ``notifier_strategy``
   to ``rabbit`` or ``qpid`` in ``glance-api.conf`` and restarting the
   service.

3. In order to retrieve object store statistics, ceilometer needs an
   access to swift with ``ResellerAdmin`` role. You should give this
   role to your ``os_username`` user for tenant ``os_tenant_name``::

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

4. Install MongoDB.

   Follow the instructions to install the MongoDB_ package for your
   operating system, then start the service.

5. Clone the ceilometer git repository to the management server::

   $ cd /opt/stack
   $ git clone https://github.com/openstack/ceilometer.git

6. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

7. Configure ceilometer.

   Ceilometer needs to know about some of the nova configuration
   options, so the simplest way to start is copying
   ``/etc/nova/nova.conf`` to ``/etc/ceilometer/ceilometer.conf``. Some
   of the logging settings used in nova break ceilometer, so they need
   to be removed. For example, as a user with ``root`` permissions::

     $ grep -v format_string /etc/nova/nova.conf > /etc/ceilometer/ceilometer.conf

   Refer to :doc:`configuration` for details about any other options
   you might want to modify before starting the service.

8. Start the collector.

   ::

     $ ./bin/ceilometer-collector

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

1. Install and configure nova.

   The collector daemon imports code from ``nova``, so it needs to be
   run on a server where nova has already been installed.

   .. note::

      Ceilometer makes extensive use of the messaging bus, but has not
      yet been tested with ZeroMQ. We recommend using Rabbit or qpid
      for now.

   The ``nova`` compute service needs the following configuration to
   be set in ``nova.conf``::

      # nova-compute configuration for ceilometer
      instance_usage_audit=True
      instance_usage_audit_period=hour
      notification_driver=nova.openstack.common.notifier.rabbit_notifier
      notification_driver=ceilometer.compute.nova_notifier

2. Clone the ceilometer git repository to the server::

   $ cd /opt/stack
   $ git clone https://github.com/openstack/ceilometer.git

4. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

5. Configure ceilometer.

   Ceilometer needs to know about some of the nova configuration
   options, so the simplest way to start is copying
   ``/etc/nova/nova.conf`` to ``/etc/ceilometer/ceilometer.conf``. Some
   of the logging settings used in nova break ceilometer, so they need
   to be removed. For example, as a user with ``root`` permissions::

     $ grep -v format_string /etc/nova/nova.conf > /etc/ceilometer/ceilometer.conf

   Refer to :doc:`configuration` for details about any other options
   you might want to modify before starting the service.

6. Start the agent.

   ::

     $ ./bin/ceilometer-agent

   .. note:: 

      The default development configuration of the agent logs to
      stderr, so you may want to run this step using a screen session
      or other tool for maintaining a long-running program in the
      background.

Installing the API Server
=========================
    
.. index::
   double: installing; API
    
.. note::
   The API server needs to be able to talk to keystone and ceilometer's
   database.

1. Install and configure nova.

   The the ceilometer api server imports code from ``nova``, so it needs to be
   run on a server where nova has already been installed.

2. Clone the ceilometer git repository to the server::

   $ cd /opt/stack
   $ git clone https://github.com/openstack/ceilometer.git

4. As a user with ``root`` permissions or ``sudo`` privileges, run the
   ceilometer installer::

   $ cd ceilometer
   $ sudo python setup.py install

5. Configure ceilometer.

   Ceilometer needs to know about some of the nova configuration
   options, so the simplest way to start is copying
   ``/etc/nova/nova.conf`` to ``/etc/ceilometer/ceilometer.conf``. Some
   of the logging settings used in nova break ceilometer, so they need
   to be removed. For example, as a user with ``root`` permissions::

     $ grep -v format_string /etc/nova/nova.conf > /etc/ceilometer/ceilometer.conf

   Refer to :doc:`configuration` for details about any other options
   you might want to modify before starting the service.

6. Start the agent.

   ::

    $ ./bin/ceilometer-api

.. note::

   The development version of the API server logs to stderr, so you
   may want to run this step using a screen session or other tool for
   maintaining a long-running program in the background.

