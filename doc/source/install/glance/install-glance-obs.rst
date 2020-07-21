Enable Image service meters for openSUSE and SUSE Linux Enterprise
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses notifications to collect Image service meters. Perform
these steps on the controller node.

Configure the Image service to use Telemetry
--------------------------------------------

* Edit the ``/etc/glance/glance-api.conf`` file and
  complete the following actions:

  * In the ``[DEFAULT]``, ``[oslo_messaging_notifications]`` sections,
    configure notifications and RabbitMQ
    message broker access:

    .. code-block:: ini

       [DEFAULT]
       ...
       transport_url = rabbit://openstack:RABBIT_PASS@controller

       [oslo_messaging_notifications]
       ...
       driver = messagingv2

    Replace ``RABBIT_PASS`` with the password you chose for
    the ``openstack`` account in ``RabbitMQ``.

Finalize installation
---------------------

* Restart the Image service:

  .. code-block:: console

     # systemctl restart openstack-glance-api.service
