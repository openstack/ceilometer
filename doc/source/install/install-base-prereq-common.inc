1. Source the ``admin`` credentials to gain access to admin-only
   CLI commands:

   .. code-block:: console

      $ . admin-openrc

2. To create the service credentials, complete these steps:

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

3. Register Gnocchi service in Keystone:

   * Create the ``gnocchi`` user:

     .. code-block:: console

        $ openstack user create --domain default --password-prompt gnocchi
        User Password:
        Repeat User Password:
        +-----------+----------------------------------+
        | Field     | Value                            |
        +-----------+----------------------------------+
        | domain_id | e0353a670a9e496da891347c589539e9 |
        | enabled   | True                             |
        | id        | 8bacd064f6434ef2b6bbfbedb79b0318 |
        | name      | gnocchi                          |
        +-----------+----------------------------------+

   * Create the ``gnocchi`` service entity:

     .. code-block:: console

        $ openstack service create --name gnocchi \
          --description "Metric Service" metric
        +-------------+----------------------------------+
        | Field       | Value                            |
        +-------------+----------------------------------+
        | description | Metric Service                   |
        | enabled     | True                             |
        | id          | 205978b411674e5a9990428f81d69384 |
        | name        | gnocchi                          |
        | type        | metric                           |
        +-------------+----------------------------------+

   * Add the ``admin`` role to the ``gnocchi`` user.

     .. code-block:: console

        $ openstack role add --project service --user gnocchi admin

     .. note::

        This command provides no output.

   * Create the Metric service API endpoints:

     .. code-block:: console

        $ openstack endpoint create --region RegionOne \
          metric public http://controller:8041
        +--------------+----------------------------------+
        | Field        | Value                            |
        +--------------+----------------------------------+
        | enabled      | True                             |
        | id           | b808b67b848d443e9eaaa5e5d796970c |
        | interface    | public                           |
        | region       | RegionOne                        |
        | region_id    | RegionOne                        |
        | service_id   | 205978b411674e5a9990428f81d69384 |
        | service_name | gnocchi                          |
        | service_type | metric                           |
        | url          | http://controller:8041           |
        +--------------+----------------------------------+

        $ openstack endpoint create --region RegionOne \
          metric internal http://controller:8041
        +--------------+----------------------------------+
        | Field        | Value                            |
        +--------------+----------------------------------+
        | enabled      | True                             |
        | id           | c7009b1c2ee54b71b771fa3d0ae4f948 |
        | interface    | internal                         |
        | region       | RegionOne                        |
        | region_id    | RegionOne                        |
        | service_id   | 205978b411674e5a9990428f81d69384 |
        | service_name | gnocchi                          |
        | service_type | metric                           |
        | url          | http://controller:8041           |
        +--------------+----------------------------------+

        $ openstack endpoint create --region RegionOne \
          metric admin http://controller:8041
        +--------------+----------------------------------+
        | Field        | Value                            |
        +--------------+----------------------------------+
        | enabled      | True                             |
        | id           | b2c00566d0604551b5fe1540c699db3d |
        | interface    | admin                            |
        | region       | RegionOne                        |
        | region_id    | RegionOne                        |
        | service_id   | 205978b411674e5a9990428f81d69384 |
        | service_name | gnocchi                          |
        | service_type | metric                           |
        | url          | http://controller:8041           |
        +--------------+----------------------------------+
