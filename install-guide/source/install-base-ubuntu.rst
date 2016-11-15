.. _install_ubuntu:

Install and configure for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
See :ref:`environment-nosql-database-ubuntu` to install and configure
MongoDB before proceeding further.

1. Create the ``ceilometer`` database:

   .. code-block:: console

      # mongo --host controller --eval '
        db = db.getSiblingDB("ceilometer");
        db.addUser({user: "ceilometer",
        pwd: "CEILOMETER_DBPASS",
        roles: [ "readWrite", "dbAdmin" ]})'

        MongoDB shell version: 2.4.x
        connecting to: controller:27017/test
        {
         "user" : "ceilometer",
         "pwd" : "72f25aeee7ad4be52437d7cd3fc60f6f",
         "roles" : [
          "readWrite",
          "dbAdmin"
          ],
         "_id" : ObjectId("5489c22270d7fad1ba631dc3")
        }

   Replace ``CEILOMETER_DBPASS`` with a suitable password.

   .. note::

      If the command fails saying you are not authorized to insert a user,
      you may need to temporarily comment out the ``auth`` option in
      the ``/etc/mongodb.conf`` file, restart the MongoDB service using
      ``service mongodb restart``, and try calling the command again.

.. include:: install-base-prereq-common.rst

Install and configure components
--------------------------------

#. Install the packages:

   .. code-block:: console

      # apt-get install ceilometer-api ceilometer-collector \
        ceilometer-agent-central ceilometer-agent-notification \
        python-ceilometerclient

.. include:: install-base-config-common.rst

Configure the Apache HTTP server
--------------------------------

#. Create the ``/etc/apache2/sites-available/ceilometer.conf`` file
   with the following content:

   .. code-block:: apache

      Listen 8777

      <VirtualHost *:8777>
          WSGIDaemonProcess ceilometer-api processes=2 threads=10 user=ceilometer group=ceilometer display-name=%{GROUP}
          WSGIProcessGroup ceilometer-api
          WSGIScriptAlias / "/var/www/cgi-bin/ceilometer/app"
          WSGIApplicationGroup %{GLOBAL}
          ErrorLog /var/log/apache2/ceilometer_error.log
          CustomLog /var/log/apache2/ceilometer_access.log combined
      </VirtualHost>

      WSGISocketPrefix /var/run/apache2

#. Enable the Telemetry service virtual hosts:

   .. code-block:: console

      # a2ensite ceilometer

Finalize installation
---------------------

#. Reload the Apache HTTP server:

   .. code-block:: console

      # service apache2 reload

#. Restart the Telemetry services:

   .. code-block:: console

      # service ceilometer-agent-central restart
      # service ceilometer-agent-notification restart
      # service ceilometer-collector restart
