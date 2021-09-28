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

.. _Gnocchi: https://gnocchi.osci.io
.. include:: install-base-prereq-common.inc

Install Gnocchi
---------------

#. Install the Gnocchi packages. Alternatively, Gnocchi can be installed using
   pip:

   .. code-block:: console

      # apt-get install gnocchi-api gnocchi-metricd python-gnocchiclient

   .. note::

      Depending on your environment size, consider installing Gnocchi
      separately as it makes extensive use of the cpu.

#. Install the uWSGI packages. The following method uses operating system
   provided packages. Another alternative would be to use pip(or pip3,
   depending on the distribution); using pip is not described in this doc:

   .. code-block:: console

      # apt-get install uwsgi-plugin-python3 uwsgi

   .. note::

      Since the provided gnocchi-api wraps around uwsgi, you need to
      make sure that uWSGI is installed if you want to use gnocchi-api
      to run Gnocchi API.
      As Gnocchi API tier runs using WSGI, it can also alternatively
      be run using Apache httpd and mod_wsgi, or any other HTTP daemon.

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

      # apt-get install ceilometer-agent-notification \
        ceilometer-agent-central

.. include:: install-base-config-common.inc

Finalize installation
---------------------

#. Restart the Telemetry services:

   .. code-block:: console

      # service ceilometer-agent-central restart
      # service ceilometer-agent-notification restart
