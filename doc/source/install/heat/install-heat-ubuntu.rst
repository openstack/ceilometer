Enable Orchestration service meters for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses notifications to collect Orchestration service meters. Perform
these steps on the controller node.

Configure the Orchestration service to use Telemetry
----------------------------------------------------

* Edit the ``/etc/heat/heat.conf`` and complete the following actions:

  * In the ``[oslo_messaging_notifications]`` sections, enable notifications:

    .. code-block:: ini

       [oslo_messaging_notifications]
       ...
       driver = messagingv2

Finalize installation
---------------------

* Restart the Orchestration service:

  .. code-block:: console

     # service heat-api restart
     # service heat-api-cfn restart
     # service heat-engine restart
