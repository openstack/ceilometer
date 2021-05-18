==============================
Installing development sandbox
==============================

In a development environment created by devstack_, Ceilometer can be tested
alongside other OpenStack services.

Configuring devstack
====================

1. Download devstack_.

2. Create a ``local.conf`` file as input to devstack.

3. The ceilometer services are not enabled by default, so they must be
   enabled in ``local.conf`` but adding the following::

     # Enable the Ceilometer devstack plugin
     enable_plugin ceilometer https://opendev.org/openstack/ceilometer.git

   By default, all ceilometer services except for ceilometer-ipmi agent will
   be enabled

4. Enable Gnocchi storage support by including the following in ``local.conf``::

     CEILOMETER_BACKEND=gnocchi

   Optionally, services which extend Ceilometer can be enabled::

     enable_plugin aodh https://opendev.org/openstack/aodh

   These plugins should be added before ceilometer.

5. ``./stack.sh``

.. _devstack: https://docs.openstack.org/devstack/latest/
