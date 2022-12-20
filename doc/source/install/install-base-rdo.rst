.. _install_rdo:

Install and configure for Red Hat Enterprise Linux and CentOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how to install and configure the
Telemetry service, code-named ceilometer, on the controller node.

Prerequisites
-------------

Before you install and configure the Telemetry service, you must
configure a target to send metering data to. The recommended endpoint
is Gnocchi_.

.. _Gnocchi: https://gnocchi.osci.io
.. include:: install-base-prereq-common.inc

Install Gnocchi
---------------

#. Install the Gnocchi packages. Alternatively, Gnocchi can be install using
   pip:

   .. code-block:: console

      # dnf install openstack-gnocchi-api openstack-gnocchi-metricd \
        python3-gnocchiclient

   .. note::

      Depending on your environment size, consider installing Gnocchi
      separately as it makes extensive use of the cpu.

#. Install the uWSGI packages. The following method uses operating system
   provided packages. Another alternative would be to use pip(or pip3,
   depending on the distribution); using pip is not described in this doc:

   .. code-block:: console

      # dnf install uwsgi-plugin-common uwsgi-plugin-python3 uwsgi

   .. note::

      Since the provided gnocchi-api wraps around uwsgi, you need to
      make sure that uWSGI is installed if you want to use gnocchi-api
      to run Gnocchi API.
      As Gnocchi API tier runs using WSGI, it can also alternatively
      be run using Apache httpd and mod_wsgi, or any other HTTP daemon.

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

#. Install the Ceilometer packages:

   .. code-block:: console

      # dnf install openstack-ceilometer-notification \
        openstack-ceilometer-central

.. include:: install-base-config-common.inc

Finalize installation
---------------------

#. Start the Telemetry services and configure them to start when the
   system boots:

   .. code-block:: console

      # systemctl enable openstack-ceilometer-notification.service \
        openstack-ceilometer-central.service
      # systemctl start openstack-ceilometer-notification.service \
        openstack-ceilometer-central.service
