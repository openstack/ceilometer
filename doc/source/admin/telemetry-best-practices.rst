Telemetry best practices
~~~~~~~~~~~~~~~~~~~~~~~~

The following are some suggested best practices to follow when deploying
and configuring the Telemetry service. The best practices are divided
into data collection and storage.

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
   <https://docs.openstack.org/ha-guide/controller-ha-telemetry.html>`_.

#. `workload_partitioning` of notification agents is only required if
   the pipeline configuration leverages transformers. It may also be enabled if
   batching is required to minimize load on the defined publisher targets. If
   transformers are not enabled, multiple agents may still be deployed without
   `workload_partitioning` and processing will be done greedily.

Data storage
------------

.. note::

   As of Newton, data storage is not recommended in ceilometer. Alarm,
   metric, and event data should be stored in aodh, gnocchi, and panko
   respectively. The following details only relate to ceilometer's legacy
   API.

#. We recommend that you avoid open-ended queries. In order to get better
   performance you can use reasonable time ranges and/or other query
   constraints for retrieving measurements.

   For example, this open-ended query might return an unpredictable amount
   of data:

   .. code-block:: console

      $ ceilometer sample-list --meter cpu -q 'resource_id=INSTANCE_ID_1'

   Whereas, this well-formed query returns a more reasonable amount of
   data, hence better performance:

   .. code-block:: console

      $ ceilometer sample-list --meter cpu -q 'resource_id=INSTANCE_ID_1;timestamp > 2015-05-01T00:00:00;timestamp < 2015-06-01T00:00:00'

   .. note::

      The number of items returned will be
      restricted to the value defined by ``default_api_return_limit`` in the
      ``ceilometer.conf`` configuration file. Alternatively, the value can
      be set per query by passing ``limit`` option in request.

#. We recommend that you install the API behind ``mod_wsgi``, as it provides
   more settings to tweak, like ``threads`` and ``processes`` in case of
   ``WSGIDaemon``.

   .. note::

      For more information on how to configure ``mod_wsgi``, see the
      `Telemetry Install Documentation
      <https://docs.openstack.org/developer/ceilometer/install/mod_wsgi.html>`__.

#. The collection service provided by the Telemetry project is not intended
   to be an archival service. Set a Time to Live (TTL) value to expire data
   and minimize the database size. If you would like to keep your data for
   longer time period, you may consider storing it in a data warehouse
   outside of Telemetry.

   .. note::

      For more information on how to set the TTL, see
      :ref:`telemetry-expiry`.

#. We recommend that you do not run MongoDB on the same node as the
   controller. Keep it on a separate node optimized for fast storage for
   better performance. Also it is advisable for the MongoDB node to have a
   lot of memory.

   .. note::

      For more information on how much memory you need, see `MongoDB
      FAQ <http://docs.mongodb.org/manual/faq/diagnostics/#how-do-i-calculate-how-much-ram-i-need-for-my-application>`__.

#. Use replica sets in MongoDB. Replica sets provide high availability
   through automatic failover. If your primary node fails, MongoDB will
   elect a secondary node to replace the primary node, and your cluster
   will remain functional.

   For more information on replica sets, see the `MongoDB replica sets
   docs <http://docs.mongodb.org/manual/tutorial/deploy-replica-set/>`__.

#. Use sharding in MongoDB. Sharding helps in storing data records across
   multiple machines and is the MongoDB’s approach to meet the demands of
   data growth.

   For more information on sharding, see the `MongoDB sharding
   docs <http://docs.mongodb.org/manual/sharding/>`__.
