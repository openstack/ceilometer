2. Source the ``admin`` credentials to gain access to admin-only
   CLI commands:

   .. code-block:: console

      $ . admin-openrc

3. To create the service credentials, complete these steps:

   * Create the ``ceilometer`` user:

     .. code-block:: console

        $ openstack user create --domain default --password-prompt ceilometer
        User Password:
        Repeat User Password:
        +-----------+----------------------------------+
        | Field     | Value                            |
        +-----------+----------------------------------+
        | domain_id | e0353a670a9e496da891347c589539e9 |
        | enabled   | True                             |
        | id        | c859c96f57bd4989a8ea1a0b1d8ff7cd |
        | name      | ceilometer                       |
        +-----------+----------------------------------+

   * Add the ``admin`` role to the ``ceilometer`` user.

     .. code-block:: console

        $ openstack role add --project service --user ceilometer admin

     .. note::

        This command provides no output.

   * Create the ``ceilometer`` service entity:

     .. code-block:: console

        $ openstack service create --name ceilometer \
          --description "Telemetry" metering
        +-------------+----------------------------------+
        | Field       | Value                            |
        +-------------+----------------------------------+
        | description | Telemetry                        |
        | enabled     | True                             |
        | id          | 5fb7fd1bb2954fddb378d4031c28c0e4 |
        | name        | ceilometer                       |
        | type        | metering                         |
        +-------------+----------------------------------+

4. Create the Telemetry service API endpoints:

   .. code-block:: console

      $ openstack endpoint create --region RegionOne \
        metering public http://controller:8777
      +--------------+----------------------------------+
      | Field        | Value                            |
      +--------------+----------------------------------+
      | enabled      | True                             |
      | id           | b808b67b848d443e9eaaa5e5d796970c |
      | interface    | public                           |
      | region       | RegionOne                        |
      | region_id    | RegionOne                        |
      | service_id   | 5fb7fd1bb2954fddb378d4031c28c0e4 |
      | service_name | ceilometer                       |
      | service_type | metering                         |
      | url          | http://controller:8777           |
      +--------------+----------------------------------+

      $ openstack endpoint create --region RegionOne \
        metering internal http://controller:8777
      +--------------+----------------------------------+
      | Field        | Value                            |
      +--------------+----------------------------------+
      | enabled      | True                             |
      | id           | c7009b1c2ee54b71b771fa3d0ae4f948 |
      | interface    | internal                         |
      | region       | RegionOne                        |
      | region_id    | RegionOne                        |
      | service_id   | 5fb7fd1bb2954fddb378d4031c28c0e4 |
      | service_name | ceilometer                       |
      | service_type | metering                         |
      | url          | http://controller:8777           |
      +--------------+----------------------------------+

      $ openstack endpoint create --region RegionOne \
        metering admin http://controller:8777
      +--------------+----------------------------------+
      | Field        | Value                            |
      +--------------+----------------------------------+
      | enabled      | True                             |
      | id           | b2c00566d0604551b5fe1540c699db3d |
      | interface    | admin                            |
      | region       | RegionOne                        |
      | region_id    | RegionOne                        |
      | service_id   | 5fb7fd1bb2954fddb378d4031c28c0e4 |
      | service_name | ceilometer                       |
      | service_type | metering                         |
      | url          | http://controller:8777           |
      +--------------+----------------------------------+
