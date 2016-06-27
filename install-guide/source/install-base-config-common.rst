2. Edit the ``/etc/ceilometer/ceilometer.conf`` file and complete
   the following actions:

   * In the ``[database]`` section, configure database access:

     .. code-block:: ini

        [database]
        ...
        connection = mongodb://ceilometer:CEILOMETER_DBPASS@controller:27017/ceilometer

     Replace ``CEILOMETER_DBPASS`` with the password you chose for the
     Telemetry service database. You must escape special characters such
     as ':', '/', '+', and '@' in the connection string in accordance
     with `RFC2396 <https://www.ietf.org/rfc/rfc2396.txt>`_.

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

        Replace ``CEILOMETER_PASS`` with the password you chose for
        the ``ceilometer`` user in the Identity service.

   * In the ``[service_credentials]`` section, configure service credentials:

     .. code-block:: ini

        [service_credentials]
        ...
        auth_type = password
        auth_url = http://controller:5000/v3
        project_domain_name = default
        user_domain_name = default
        project_name = service
        username = ceilometer
        password = CEILOMETER_PASS
        interface = internalURL
        region_name = RegionOne

     Replace ``CEILOMETER_PASS`` with the password you chose for
     the ``ceilometer`` user in the Identity service.
