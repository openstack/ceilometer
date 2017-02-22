Enable Block Storage meters for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses notifications to collect Block Storage service meters.
Perform these steps on the controller and Block Storage nodes.

.. note::

   Your environment must include the Block Storage service.

Configure Cinder to use Telemetry
---------------------------------

Edit the ``/etc/cinder/cinder.conf`` file and complete the
following actions:

* In the ``[oslo_messaging_notifications]`` section, configure notifications:

  .. code-block:: ini

     [oslo_messaging_notifications]
     ...
     driver = messagingv2

.. include:: install-cinder-config-common.inc

Finalize installation
---------------------

#. Restart the Block Storage services on the controller node:

   .. code-block:: console

      # service cinder-api restart
      # service cinder-scheduler restart

#. Restart the Block Storage services on the storage nodes:

   .. code-block:: console

      # service cinder-volume restart
