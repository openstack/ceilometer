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

===============================
 Installing development sandbox
===============================

Ceilometer has several daemons. The basic are: :term:`polling agent` running
either on the Nova compute node(s) or :term:`polling agent` running on the
central management node(s), :term:`notification agent` running on the cloud's
management node(s).

In a development environment created by devstack_, these services are
typically running on the same server.


Configuring devstack
====================

.. index::
   double: installing; devstack

1. Download devstack_.

2. Create a ``local.conf`` file as input to devstack.

3. Ceilometer makes extensive use of the messaging bus, but has not
   yet been tested with ZeroMQ. We recommend using Rabbit for
   now. By default, RabbitMQ will be used by devstack.

4. The ceilometer services are not enabled by default, so they must be
   enabled in ``local.conf`` before running ``stack.sh``.

   This example ``local.conf`` file shows all of the settings required for
   ceilometer::

      [[local|localrc]]
      # Enable the Ceilometer devstack plugin
      enable_plugin ceilometer https://git.openstack.org/openstack/ceilometer.git

   By default, all ceilometer services except for ceilometer-ipmi agent will
   be enabled

.. _devstack: http://www.devstack.org/
