Enable Compute service meters for openSUSE and SUSE Linux Enterprise
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses a combination of notifications and an agent to collect
Compute meters. Perform these steps on each compute node.

Install and configure components
--------------------------------

#. Install the packages:

   .. code-block:: console

      # zypper install openstack-ceilometer-agent-compute
      # zypper install openstack-ceilometer-agent-ipmi (optional)

.. include:: install-compute-common.inc

Finalize installation
---------------------

#. Start the agent and configure it to start when the system boots:

   .. code-block:: console

      # systemctl enable openstack-ceilometer-agent-compute.service
      # systemctl start openstack-ceilometer-agent-compute.service
      # systemctl enable openstack-ceilometer-agent-ipmi.service (optional)
      # systemctl start openstack-ceilometer-agent-ipmi.service (optional)

#. Restart the Compute service:

   .. code-block:: console

      # systemctl restart openstack-nova-compute.service
