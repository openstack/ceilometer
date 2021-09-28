3. Create the database for Gnocchi's indexer:

   * Use the database access client to connect to the database
     server as the ``root`` user:

     .. code-block:: console

        $ mysql -u root -p

   * Create the ``gnocchi`` database:

     .. code-block:: console

        CREATE DATABASE gnocchi;

   * Grant proper access to the ``gnocchi`` database:

     .. code-block:: console

        GRANT ALL PRIVILEGES ON gnocchi.* TO 'gnocchi'@'localhost' \
          IDENTIFIED BY 'GNOCCHI_DBPASS';
        GRANT ALL PRIVILEGES ON gnocchi.* TO 'gnocchi'@'%' \
          IDENTIFIED BY 'GNOCCHI_DBPASS';

     Replace ``GNOCCHI_DBPASS`` with a suitable password.

   * Exit the database access client.

4. Edit the ``/etc/gnocchi/gnocchi.conf`` file and add Keystone options:

   * In the ``[api]`` section, configure gnocchi to use keystone:

     .. code-block:: ini

        [api]
        auth_mode = keystone
        port = 8041
        uwsgi_mode = http-socket

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

   * In the ``[indexer]`` section, configure database access:

     .. code-block:: ini

        [indexer]
        url = mysql+pymysql://gnocchi:GNOCCHI_DBPASS@controller/gnocchi

     Replace ``GNOCCHI_DBPASS`` with the password you chose for Gnocchi's
     indexer database.

   * In the ``[storage]`` section, configure location to store metric data.
     In this case, we will store it to the local file system. See Gnocchi
     documenation for a list of more durable and performant drivers:

     .. code-block:: ini

        [storage]
	# coordination_url is not required but specifying one will improve
	# performance with better workload division across workers.
        coordination_url = redis://controller:6379
        file_basepath = /var/lib/gnocchi
        driver = file

5. Initialize Gnocchi:

   .. code-block:: console

      gnocchi-upgrade
