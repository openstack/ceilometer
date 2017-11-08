.. _install_obs:

Install and configure for openSUSE and SUSE Linux Enterprise
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

      # zypper install openstack-gnocchi-api openstack-gnocchi-metricd \
        python-gnocchiclient

   .. note::

      Depending on your environment size, consider installing Gnocchi
      separately as it makes extensive use of the cpu.

.. include:: install-gnocchi.inc

Finalize Gnocchi installation
-----------------------------

#. Start the Gnocchi services and configure them to start when the
   system boots:

   .. code-block:: console

      # systemctl enable openstack-gnocchi-api.service \
        openstack-gnocchi-metricd.service
      # systemctl start openstack-gnocchi-api.service \
        openstack-gnocchi-metricd.service

Install and configure components
--------------------------------

#. Install the packages:

   .. code-block:: console

      # zypper install openstack-ceilometer-agent-notification \
        openstack-ceilometer-agent-central

.. include:: install-base-config-common.inc

Finalize installation
---------------------

#. Start the Telemetry services and configure them to start when the
   system boots:

   .. code-block:: console

      # systemctl enable openstack-ceilometer-agent-notification.service \
        openstack-ceilometer-agent-central.service
      # systemctl start openstack-ceilometer-agent-notification.service \
        openstack-ceilometer-agent-central.service
