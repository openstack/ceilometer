Enable Image service meters for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses notifications to collect Image service meters. Perform
these steps on the controller node.

Configure the Image service to use Telemetry
--------------------------------------------

* Edit the ``/etc/glance/glance-api.conf`` and
  ``/etc/glance/glance-registry.conf`` files and
  complete the following actions:

  * In the ``[DEFAULT]``, ``[oslo_messaging_notifications]``, and
    ``[oslo_messaging_rabbit]`` sections, configure notifications and RabbitMQ
    message broker access:

    .. code-block:: ini

       [DEFAULT]
       ...
       rpc_backend = rabbit

       [oslo_messaging_notifications]
       ...
       driver = messagingv2

       [oslo_messaging_rabbit]
       ...
       rabbit_host = controller
       rabbit_userid = openstack
       rabbit_password = RABBIT_PASS

    Replace ``RABBIT_PASS`` with the password you chose for
    the ``openstack`` account in ``RabbitMQ``.

Finalize installation
---------------------

* Restart the Image service:

  .. code-block:: console

     # service glance-registry restart
     # service glance-api restart
