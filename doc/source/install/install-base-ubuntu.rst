.. _install_ubuntu:

Install and configure for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how to install and configure the
Telemetry service, code-named ceilometer, on the controller node.

Prerequisites
-------------

Before you install and configure the Telemetry service, you must
configure a target to send metering data to. The recommended endpoint
is Gnocchi_. To enable Gnocchi, please see its install guide.

.. _Gnocchi: http://gnocchi.xyz
.. include:: install-base-prereq-common.inc

Install and configure components
--------------------------------

#. Install the packages:

   .. code-block:: console

      # apt-get install ceilometer-agent-notification \
        ceilometer-agent-central python-ceilometerclient

.. include:: install-base-config-common.inc

Finalize installation
---------------------

#. Restart the Telemetry services:

   .. code-block:: console

      # service ceilometer-agent-central restart
      # service ceilometer-agent-notification restart
