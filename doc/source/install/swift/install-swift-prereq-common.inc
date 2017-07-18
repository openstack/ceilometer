Prerequisites
-------------

The Telemetry service requires access to the Object Storage service
using the ``ResellerAdmin`` role. Perform these steps on the controller
node.

#. Source the ``admin`` credentials to gain access to admin-only
   CLI commands.

   .. code-block:: console

      $ . admin-openrc

#. Create the ``ResellerAdmin`` role:

   .. code-block:: console

      $ openstack role create ResellerAdmin
      +-----------+----------------------------------+
      | Field     | Value                            |
      +-----------+----------------------------------+
      | domain_id | None                             |
      | id        | 462fa46c13fd4798a95a3bfbe27b5e54 |
      | name      | ResellerAdmin                    |
      +-----------+----------------------------------+

#. Add the ``ResellerAdmin`` role to the ``ceilometer`` user:

   .. code-block:: console

      $ openstack role add --project service --user ceilometer ResellerAdmin

   .. note::

      This command provides no output.
