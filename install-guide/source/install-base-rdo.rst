.. _install_rdo:

Install and configure for Red Hat Enterprise Linux and CentOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section describes how to install and configure the
Telemetry service, code-named ceilometer, on the controller node.

This section assumes that you already have a working OpenStack
environment with at least the following components installed:
Compute, Image Service, Identity.

Prerequisites
-------------

Before you install and configure the Telemetry service, you must
create a database, service credentials, and API endpoints. However,
unlike other services, the Telemetry service uses a NoSQL database.
See :ref:`environment-nosql-database-rdo` to install and configure
MongoDB before proceeding further.

1. Create the ``ceilometer`` database:

   .. code-block:: console

      # mongo --host controller --eval '
        db = db.getSiblingDB("ceilometer");
        db.createUser({user: "ceilometer",
        pwd: "CEILOMETER_DBPASS",
        roles: [ "readWrite", "dbAdmin" ]})'

        MongoDB shell version: 2.6.x
        connecting to: controller:27017/test
        Successfully added user: { "user" : "ceilometer", "roles" : [ "readWrite", "dbAdmin" ] }

   Replace ``CEILOMETER_DBPASS`` with a suitable password.

.. include:: install-base-prereq-common.rst

Install and configure components
--------------------------------

1. Install the packages:

   .. code-block:: console

      # yum install openstack-ceilometer-api \
        openstack-ceilometer-collector openstack-ceilometer-notification \
        openstack-ceilometer-central python-ceilometerclient

.. include:: install-base-config-common.rst

Configure the Apache HTTP server
--------------------------------

* Create the ``/etc/httpd/conf.d/wsgi-ceilometer.conf`` file with
  the following content:

  .. code-block:: apache

     Listen 8777

     <VirtualHost *:8777>
         WSGIDaemonProcess ceilometer-api processes=2 threads=10 user=ceilometer group=ceilometer display-name=%{GROUP}
         WSGIProcessGroup ceilometer-api
         WSGIScriptAlias / /usr/lib/python2.7/site-packages/ceilometer/api/app.wsgi
         WSGIApplicationGroup %{GLOBAL}
         ErrorLog /var/log/httpd/ceilometer_error.log
         CustomLog /var/log/httpd/ceilometer_access.log combined
     </VirtualHost>

     WSGISocketPrefix /var/run/httpd

Finalize installation
---------------------

#. Reload the Apache HTTP server:

   .. code-block:: console

      # systemctl reload httpd.service

#. Start the Telemetry services and configure them to start when the
   system boots:

   .. code-block:: console

      # systemctl enable openstack-ceilometer-notification.service \
        openstack-ceilometer-central.service \
        openstack-ceilometer-collector.service
      # systemctl start openstack-ceilometer-notification.service \
        openstack-ceilometer-central.service \
        openstack-ceilometer-collector.service
