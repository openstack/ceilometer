2. Edit the ``/etc/ceilometer/ceilometer.conf`` file and
   complete the following actions:

   * In the ``[DEFAULT]`` and ``[oslo_messaging_rabbit]`` sections,
     configure ``RabbitMQ`` message queue access:

     .. code-block:: ini

        [DEFAULT]
        ...
        rpc_backend = rabbit

        [oslo_messaging_rabbit]
        ...
        rabbit_host = controller
        rabbit_userid = openstack
        rabbit_password = RABBIT_PASS

     Replace ``RABBIT_PASS`` with the password you chose for the
     ``openstack`` account in ``RabbitMQ``.

   * In the ``[DEFAULT]`` and ``[keystone_authtoken]`` sections,
     configure Identity service access:

     .. code-block:: ini

        [DEFAULT]
        ...
        auth_strategy = keystone

        [keystone_authtoken]
        ...
        auth_uri = http://controller:5000
        auth_url = http://controller:35357
        memcached_servers = controller:11211
        auth_type = password
        project_domain_name = default
        user_domain_name = default
        project_name = service
        username = ceilometer
        password = CEILOMETER_PASS

     Replace ``CEILOMETER_PASS`` with the password you chose for the
     Telemetry service database.

   * In the ``[service_credentials]`` section, configure service
     credentials:

     .. code-block:: ini

        [service_credentials]
        ...
        auth_url = http://controller:5000
        project_domain_id = default
        user_domain_id = default
        auth_type = password
        username = ceilometer
        project_name = service
        password = CEILOMETER_PASS
        interface = internalURL
        region_name = RegionOne

     Replace ``CEILOMETER_PASS`` with the password you chose for
     the ``ceilometer`` user in the Identity service.

Configure Compute to use Telemetry
----------------------------------

* Edit the ``/etc/nova/nova.conf`` file and configure
  notifications in the ``[DEFAULT]`` section:

  .. code-block:: ini

     [DEFAULT]
     ...
     instance_usage_audit = True
     instance_usage_audit_period = hour
     notify_on_state_change = vm_and_task_state

     [oslo_messaging_notifications]
     ...
     driver = messagingv2
