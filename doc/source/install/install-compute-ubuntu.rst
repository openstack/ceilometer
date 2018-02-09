Enable Compute service meters for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses a combination of notifications and an agent to collect
Compute meters. Perform these steps on each compute node.

Install and configure components
--------------------------------

#. Install the packages:

   .. code-block:: console

      # apt-get install ceilometer-agent-compute
      # apt-get install ceilometer-agent-ipmi (optional)

.. include:: install-compute-common.inc

Finalize installation
---------------------

#. Restart the agent:

   .. code-block:: console

      # service ceilometer-agent-compute restart
      # service ceilometer-agent-ipmi restart (optional)

#. Restart the Compute service:

   .. code-block:: console

      # service nova-compute restart
