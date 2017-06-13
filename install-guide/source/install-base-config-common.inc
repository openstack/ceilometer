2. Edit the ``/etc/ceilometer/ceilometer.conf`` file and complete
   the following actions:

   * Configure Gnocchi connection:

     .. code-block:: ini

        [DEFAULT]
        ...
        meter_dispatchers=gnocchi
        event_dispatchers=gnocchi

        [dispatcher_gnocchi]
        # filter out Gnocchi-related activity meters (Swift driver)
        filter_service_activity = False
        # default metric storage archival policy
        archive_policy = low

     .. note::

        It is possible forego the collector service by modifying the
        pipeline.yaml to use the ``gnocchi://`` publisher rather than
        ``notifier://``. Doing so will minimise resource requirements.
        In this case, dispatchers do not need to be added to conf file.

   * In the ``[DEFAULT]`` section,
     configure ``RabbitMQ`` message queue access:

     .. code-block:: ini

        [DEFAULT]
        ...
        transport_url = rabbit://openstack:RABBIT_PASS@controller

     Replace ``RABBIT_PASS`` with the password you chose for the
     ``openstack`` account in ``RabbitMQ``.

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

3. Edit the ``/etc/gnocchi/gnocchi.conf`` file and add Keystone options:

   * In the ``[api]`` section, configure gnocchi to use keystone:

     .. code-block:: ini

        [api]
        auth_mode = keystone

   * In the ``[keystone_authtoken]`` section, configure keystone
     authentication:

     .. code-block:: ini

        [keystone_authtoken]
        ...
        auth_type = password
        auth_url = http://controller:5000/v3
        project_domain_name = Default
        user_domain_name = Default
        project_name = service
        username = gnocchi
        password = GNOCCHI_PASS
        interface = internalURL
        region_name = RegionOne

     Replace ``GNOCCHI_PASS`` with the password you chose for
     the ``gnocchi`` user in the Identity service.

4. Create Ceilometer resources in Gnocchi. Gnocchi should be running by this
   stage:

   .. code-block:: console

      # ceilometer-upgrade --skip-metering-database
