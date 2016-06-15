.. _environment-nosql-database-ubuntu:

NoSQL database for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~

The Telemetry service uses a NoSQL database to store information. The database
typically runs on the controller node. The procedures in this guide use
MongoDB.

Install and configure components
--------------------------------

1. Install the MongoDB packages:

   .. code-block:: console

      # apt-get install mongodb-server mongodb-clients python-pymongo

2. Edit the ``/etc/mongodb.conf`` file and complete the following
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

* If you change the journaling configuration, stop the MongoDB
  service, remove the initial journal files, and start the service:

  .. code-block:: console

     # service mongodb stop
     # rm /var/lib/mongodb/journal/prealloc.*
     # service mongodb start
