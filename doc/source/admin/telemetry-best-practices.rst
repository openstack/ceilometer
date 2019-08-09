Telemetry best practices
~~~~~~~~~~~~~~~~~~~~~~~~

The following are some suggested best practices to follow when deploying
and configuring the Telemetry service.

Data collection
---------------

#. The Telemetry service collects a continuously growing set of data. Not
   all the data will be relevant for an administrator to monitor.

   -  Based on your needs, you can edit the ``polling.yaml`` and
      ``pipeline.yaml`` configuration files to include select meters to
      generate or process

   -  By default, Telemetry service polls the service APIs every 10
      minutes. You can change the polling interval on a per meter basis by
      editing the ``polling.yaml`` configuration file.

      .. warning::

         If the polling interval is too short, it will likely increase the
         stress on the service APIs.

#. If polling many resources or at a high frequency, you can add additional
   central and compute agents as necessary. The agents are designed to scale
   horizontally. For more information refer to the `high availability guide
   <https://docs.openstack.org/ha-guide/>`_.

   .. note::

      The High Availability Guide is a work in progress and is changing
      rapidly while testing continues.
