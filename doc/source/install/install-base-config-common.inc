2. Edit the ``/etc/ceilometer/pipeline.yaml`` file and complete
   the following section:

   * Configure Gnocchi connection:

     .. code-block:: yaml

        publishers:
            # set address of Gnocchi
            # + filter out Gnocchi-related activity meters (Swift driver)
            # + set default archive policy
            - gnocchi://?filter_project=service&archive_policy=low

3. Edit the ``/etc/ceilometer/ceilometer.conf`` file and complete
   the following actions:

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
        project_domain_id = default
        user_domain_id = default
        project_name = service
        username = ceilometer
        password = CEILOMETER_PASS
        interface = internalURL
        region_name = RegionOne

     Replace ``CEILOMETER_PASS`` with the password you chose for
     the ``ceilometer`` user in the Identity service.

4. Create Ceilometer resources in Gnocchi. Gnocchi should be running by this
   stage:

   .. code-block:: console

      # ceilometer-upgrade
