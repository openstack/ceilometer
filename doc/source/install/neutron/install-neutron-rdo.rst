Enable Networking service meters for Red Hat Enterprise Linux and CentOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses notifications to collect Networking service meters. Perform
these steps on the controller node.

Configure the Networking service to use Telemetry
-------------------------------------------------

* Edit the ``/etc/neutron/neutron.conf`` and complete the following actions:

  * In the ``[oslo_messaging_notifications]`` sections, enable notifications:

    .. code-block:: ini

       [oslo_messaging_notifications]
       ...
       driver = messagingv2

Finalize installation
---------------------

* Restart the Networking service:

  .. code-block:: console

     # systemctl restart neutron-server.service
