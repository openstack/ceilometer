.. _install_ubuntu:

Install and configure for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how to install and configure the
Telemetry service, code-named ceilometer, on the controller node.

Prerequisites
-------------

Before you install and configure the Telemetry service, you must
configure a target to send metering data to. The recommended endpoint
is Gnocchi_.

.. _Gnocchi: http://gnocchi.xyz
.. include:: install-base-prereq-common.inc

Install Gnocchi
---------------

#. Install the Gnocchi packages. Alternatively, Gnocchi can be install using
   pip:

   .. code-block:: console

      # apt-get install gnocchi-api gnocchi-metricd python-gnocchiclient

   .. note::

      Depending on your environment size, consider installing Gnocchi
      separately as it makes extensive use of the cpu.

.. include:: install-gnocchi.inc

Finalize Gnocchi installation
-----------------------------

#. Restart the Gnocchi services:

   .. code-block:: console

      # service gnocchi-api restart
      # service gnocchi-metricd restart

Install and configure components
--------------------------------

#. Install the ceilometer packages:

   .. code-block:: console

      # apt-get install ceilometer-collector \
        ceilometer-agent-central ceilometer-agent-notification \

.. include:: install-base-config-common.inc

Finalize installation
---------------------

#. Restart the Telemetry services:

   .. code-block:: console

      # service ceilometer-agent-central restart
      # service ceilometer-agent-notification restart
      # service ceilometer-collector restart
