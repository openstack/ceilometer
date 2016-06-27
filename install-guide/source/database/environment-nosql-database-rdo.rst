.. _environment-nosql-database-rdo:

NoSQL database for Red Hat Enterprise Linux and CentOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Telemetry service uses a NoSQL database to store information. The database
typically runs on the controller node. The procedures in this guide use
MongoDB.

Install and configure components
--------------------------------

1. Install the MongoDB packages:

   .. code-block:: console

      # yum install mongodb-server mongodb

2. Edit the ``/etc/mongod.conf`` file and complete the following
   actions:

   * Configure the ``bind_ip`` key to use the management interface
     IP address of the controller node.

     .. code-block:: ini

        bind_ip = 10.0.0.11

   * By default, MongoDB creates several 1 GB journal files
     in the ``/var/lib/mongodb/journal`` directory.
     If you want to reduce the size of each journal file to
     128 MB and limit total journal space consumption to 512 MB,
     assert the ``smallfiles`` key:

     .. code-block:: ini

        smallfiles = true

     You can also disable journaling. For more information, see the
     `MongoDB manual <http://docs.mongodb.org/manual/>`__.

Finalize installation
---------------------

* Start the MongoDB service and configure it to start when the system boots:

  .. code-block:: console

     # systemctl enable mongod.service
     # systemctl start mongod.service
