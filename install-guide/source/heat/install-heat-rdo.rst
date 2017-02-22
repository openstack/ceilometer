Enable Orchestration service meters for Red Hat Enterprise Linux and CentOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

     # systemctl restart openstack-heat-api.service \
       openstack-heat-api-cfn.service openstack-heat-engine.service
