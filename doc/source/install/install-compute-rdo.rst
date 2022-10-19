Enable Compute service meters for Red Hat Enterprise Linux and CentOS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses a combination of notifications and an agent to collect
Compute meters. Perform these steps on each compute node.

Install and configure components
--------------------------------

#. Install the packages:

   .. code-block:: console

      # dnf install openstack-ceilometer-compute
      # dnf install openstack-ceilometer-ipmi (optional)

.. include:: install-compute-common.inc

Finalize installation
---------------------

#. Start the agent and configure it to start when the system boots:

   .. code-block:: console

      # systemctl enable openstack-ceilometer-compute.service
      # systemctl start openstack-ceilometer-compute.service
      # systemctl enable openstack-ceilometer-ipmi.service (optional)
      # systemctl start openstack-ceilometer-ipmi.service (optional)

#. Restart the Compute service:

   .. code-block:: console

      # systemctl restart openstack-nova-compute.service
