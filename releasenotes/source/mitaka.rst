====================
Mitaka Release Notes
====================

6.0.0
=====

New Features
------------

.. releasenotes/notes/batch-messaging-d126cc525879d58e.yaml @ c5895d2c6efc6676679e6973c06b85c0c3a10585

- Add support for batch processing of messages from queue. This will allow the collector and notification agent to grab multiple messages per thread to enable more efficient processing.

.. releasenotes/notes/compute-discovery-interval-d19f7c9036a8c186.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- To minimise load on Nova API, an additional configuration option was added to control discovery interval vs metric polling interval. If resource_update_interval option is configured in compute section, the compute agent will discover new instances based on defined interval. The agent will continue to poll the discovered instances at the interval defined by pipeline.

.. releasenotes/notes/configurable-data-collector-e247aadbffb85243.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- [`bug 1480333 <https://bugs.launchpad.net/ceilometer/+bug/1480333>`_] Support ability to configure collector to capture events or meters mutally exclusively, rather than capturing both always.

.. releasenotes/notes/cors-support-70c33ba1f6825a7b.yaml @ c5895d2c6efc6676679e6973c06b85c0c3a10585

- Support for CORS is added. More information can be found [`here <http://specs.openstack.org/openstack/openstack-specs/specs/cors-support.html>`_]

.. releasenotes/notes/gnocchi-cache-1d8025dfc954f281.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- Support resource caching in Gnocchi dispatcher to improve write performance to avoid additional queries.

.. releasenotes/notes/gnocchi-client-42cd992075ee53ab.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- Gnocchi dispatcher now uses client rather than direct http requests

.. releasenotes/notes/gnocchi-host-metrics-829bcb965d8f2533.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- [`bug 1518338 <https://bugs.launchpad.net/ceilometer/+bug/1518338>`_] Add support for storing SNMP metrics in Gnocchi.This functionality requires Gnocchi v2.1.0 to be installed.

.. releasenotes/notes/keystone-v3-fab1e257c5672965.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- Add support for Keystone v3 authentication

.. releasenotes/notes/remove-alarms-4df3cdb4f1fb5faa.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- Ceilometer alarms code is now fully removed from code base. Equivalent functionality is handled by Aodh.  

.. releasenotes/notes/remove-cadf-http-f8449ced3d2a29d4.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- Support for CADF-only payload in HTTP dispatcher is dropped as audit middleware in pyCADF was dropped in Kilo cycle.

.. releasenotes/notes/remove-eventlet-6738321434b60c78.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- Remove eventlet from Ceilometer in favour of threaded approach

.. releasenotes/notes/remove-rpc-collector-d0d0a354140fd107.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- RPC collector support is dropped. The queue-based notifier publisher and collector was added as the recommended alternative as of Icehouse cycle.

.. releasenotes/notes/support-lbaasv2-polling-c830dd49bcf25f64.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- Support for polling Neutron's LBaaS v2 API was added as v1 API in Neutron is deprecated. The same metrics are available between v1 and v2.

.. releasenotes/notes/support-snmp-cpu-util-5c1c7afb713c1acd.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- [`bug 1513731 <https://bugs.launchpad.net/ceilometer/+bug/1513731>`_] Add support for hardware cpu_util in snmp.yaml

.. releasenotes/notes/support-unique-meter-query-221c6e0c1dc1b726.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- [`bug 1506959 <https://bugs.launchpad.net/ceilometer/+bug/1506959>`_] Add support to query unique set of meter names rather than meters associated with each resource. The list is available by adding unique=True option to request.


Known Issues
------------

.. releasenotes/notes/support-lbaasv2-polling-c830dd49bcf25f64.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- Neutron API is not designed to be polled against. When polling against Neutron is enabled, Ceilometer's polling agents may generage a significant load against the Neutron API. It is recommended that a dedicated API be enabled for polling while Neutron's API is improved to handle polling.


Upgrade Notes
-------------

.. releasenotes/notes/always-requeue-7a2df9243987ab67.yaml @ 244439979fd28ecb0c76d132f0be784c988b54c8

- The options 'requeue_event_on_dispatcher_error' and 'requeue_sample_on_dispatcher_error' have been enabled and removed.

.. releasenotes/notes/batch-messaging-d126cc525879d58e.yaml @ c5895d2c6efc6676679e6973c06b85c0c3a10585

- batch_size and batch_timeout configuration options are added to both [notification] and [collector] sections of configuration. The batch_size controls the number of messages to grab before processing. Similarly, the batch_timeout defines the wait time before processing.

.. releasenotes/notes/cors-support-70c33ba1f6825a7b.yaml @ c5895d2c6efc6676679e6973c06b85c0c3a10585

- The api-paste.ini file can be modified to include or exclude the CORs middleware. Additional configurations can be made to middleware as well.

.. releasenotes/notes/gnocchi-client-42cd992075ee53ab.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- gnocchiclient library is now a requirement if using ceilometer+gnocchi.

.. releasenotes/notes/gnocchi-orchestration-3497c689268df0d1.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- gnocchi_resources.yaml in Ceilometer should be updated.

.. releasenotes/notes/improve-events-rbac-support-f216bd7f34b02032.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- To utilize the new policy support. The policy.json file should be updated accordingly. The pre-existing policy.json file will continue to function as it does if policy changes are not required.

.. releasenotes/notes/index-events-mongodb-63cb04200b03a093.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- Run db-sync to add new indices.

.. releasenotes/notes/remove-cadf-http-f8449ced3d2a29d4.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- audit middleware in keystonemiddleware library should be used for similar support.

.. releasenotes/notes/remove-rpc-collector-d0d0a354140fd107.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- Pipeline.yaml files for agents should be updated to notifier:// or udp:// publishers. The rpc:// publisher is no longer supported.

.. releasenotes/notes/support-lbaasv2-polling-c830dd49bcf25f64.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- By default, Ceilometer will poll the v2 API. To poll legacy v1 API, add neutron_lbaas_version=v1 option to configuration file.


Critical Issues
---------------

.. releasenotes/notes/always-requeue-7a2df9243987ab67.yaml @ 244439979fd28ecb0c76d132f0be784c988b54c8

- The previous configuration options default for 'requeue_sample_on_dispatcher_error' and 'requeue_event_on_dispatcher_error' allowed to lose data very easily: if the dispatcher failed to send data to the backend (e.g. Gnocchi is down), then the dispatcher raised and the data were lost forever. This was completely unacceptable, and nobody should be able to configure Ceilometer in that way."

.. releasenotes/notes/fix-agent-coordination-a7103a78fecaec24.yaml @ e84a10882a9b682ff41c84e8bf4ee2497e7e7a31

- [`bug 1533787 <https://bugs.launchpad.net/ceilometer/+bug/1533787>`_] Fix an issue where agents are not properly getting registered to group when multiple notification agents are deployed. This can result in bad transformation as the agents are not coordinated. It is still recommended to set heartbeat_timeout_threshold = 0 in [oslo_messaging_rabbit] section when deploying multiple agents.

.. releasenotes/notes/thread-safe-matching-4a635fc4965c5d4c.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- [`bug 1519767 <https://bugs.launchpad.net/ceilometer/+bug/1519767>`_] fnmatch functionality in python <= 2.7.9 is not threadsafe. this issue and  its potential race conditions are now patched.


Bug Fixes
---------

.. releasenotes/notes/aggregator-transformer-timeout-e0f42b6c96aa7ada.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- [`bug 1531626 <https://bugs.launchpad.net/ceilometer/+bug/1531626>`_] Ensure aggregator transformer timeout is honoured if size is not provided.

.. releasenotes/notes/cache-json-parsers-888307f3b6b498a2.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- [`bug 1550436 <https://bugs.launchpad.net/ceilometer/+bug/1550436>`_] Cache json parsers when building parsing logic to handle event and meter definitions. This will improve agent startup and setup time.

.. releasenotes/notes/event-type-race-c295baf7f1661eab.yaml @ 0e3ae8a667d9b9d6e19a7515854eb1703fc05013

- [`bug 1254800 <https://bugs.launchpad.net/ceilometer/+bug/1254800>`_] Add better support to catch race conditions when creating event_types

.. releasenotes/notes/fix-aggregation-transformer-9472aea189fa8f65.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- [`bug 1539163 <https://bugs.launchpad.net/ceilometer/+bug/1539163>`_] Add ability to define whether to use first or last timestamps when aggregating samples. This will allow more flexibility when chaining transformers.

.. releasenotes/notes/fix-floatingip-pollster-f5172060c626b19e.yaml @ 1f9f4e1072a5e5037b93734bafcc65e4211eb19f

- [`bug 1536338 <https://bugs.launchpad.net/ceilometer/+bug/1536338>`_] Patch was added to fix the broken floatingip pollster that polled data from nova api, but since the nova api filtered the data by tenant, ceilometer was not getting any data back. The fix changes the pollster to use the neutron api instead to get the floating ip info.

.. releasenotes/notes/fix-network-lb-bytes-sample-5dec2c6f3a8ae174.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- [`bug 1530793 <https://bugs.launchpad.net/ceilometer/+bug/1530793>`_] network.services.lb.incoming.bytes meter was previous set to incorrect type. It should be a gauge meter.

.. releasenotes/notes/gnocchi-cache-b9ad4d85a1da8d3f.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- [`bug 255569 <https://bugs.launchpad.net/ceilometer/+bug/255569>`_] Fix caching support in Gnocchi dispatcher. Added better locking support to enable smoother cache access.

.. releasenotes/notes/gnocchi-orchestration-3497c689268df0d1.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- Fix samples from Heat to map to correct Gnocchi resource type

.. releasenotes/notes/gnocchi-udp-collector-00415e6674b5cc0f.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- [`bug 1523124 <https://bugs.launchpad.net/ceilometer/+bug/1523124>`_] Fix gnocchi dispatcher to support UDP collector

.. releasenotes/notes/handle-malformed-resource-definitions-ad4f69f898ced34d.yaml @ 02b1e1399bf885d03113a1cc125b1f97ed5540b9

- [`bug 1542189 <https://bugs.launchpad.net/ceilometer/+bug/1542189>`_] Handle malformed resource definitions in gnocchi_resources.yaml gracefully. Currently we raise an exception once we hit a bad resource and skip the rest. Instead the patch skips the bad resource and proceeds with rest of the definitions.

.. releasenotes/notes/improve-events-rbac-support-f216bd7f34b02032.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- [`bug 1504495 <https://bugs.launchpad.net/ceilometer/+bug/1504495>`_] Configure ceilometer to handle policy.json rules when possible.

.. releasenotes/notes/index-events-mongodb-63cb04200b03a093.yaml @ 1689e7053f4e7587a2b836035cdfa4fda56667fc

- [`bug 1526793 <https://bugs.launchpad.net/ceilometer/+bug/1526793>`_] Additional indices were added to better support querying of event data.

.. releasenotes/notes/lookup-meter-def-vol-correctly-0122ae429275f2a6.yaml @ 903a0a527cb240cfd9462b7f56d3463db7128993

- [`bug 1536699 <https://bugs.launchpad.net/ceilometer/+bug/1536699>`_] Patch to fix volume field lookup in meter definition file. In case the field is missing in the definition, it raises a keyerror and aborts. Instead we should skip the missing field meter and continue with the rest of the definitions.

.. releasenotes/notes/mongodb-handle-large-numbers-7c235598ca700f2d.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- [`bug 1532661 <https://bugs.launchpad.net/ceilometer/+bug/1532661>`_] Fix statistics query failures due to large numbers stored in MongoDB. Data from MongoDB is returned as Int64 for big numbers when int and float types are expected. The data is cast to appropriate type to handle large data.

.. releasenotes/notes/skip-duplicate-meter-def-0420164f6a95c50c.yaml @ 0c6f11cf88bf1a13a723879de46ec616678d2e0b

- [`bug 1536498 <https://bugs.launchpad.net/ceilometer/+bug/1536498>`_] Patch to fix duplicate meter definitions causing duplicate samples. If a duplicate is found, log a warning and skip the meter definition. Note that the first occurance of a meter will be used and any following duplicates will be skipped from processing.

.. releasenotes/notes/sql-query-optimisation-ebb2233f7a9b5d06.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- [`bug 1506738 <https://bugs.launchpad.net/ceilometer/+bug/1506738>`_] [`bug 1509677 <https://bugs.launchpad.net/ceilometer/+bug/1509677>`_] Optimise SQL backend queries to minimise query load

.. releasenotes/notes/support-None-query-45abaae45f08eda4.yaml @ e6fa0a84d1f7a326881f3587718f1df743b8585f

- [`bug 1388680 <https://bugs.launchpad.net/ceilometer/+bug/1388680>`_] Suppose ability to query for None value when using SQL backend.


Other Notes
-----------

.. releasenotes/notes/configurable-data-collector-e247aadbffb85243.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- Configure individual dispatchers by specifying meter_dispatchers and event_dispatchers in configuration file.

.. releasenotes/notes/gnocchi-cache-1d8025dfc954f281.yaml @ f24ea44401b8945c9cb8a34b2aedebba3c040691

- A dogpile.cache supported backend is required to enable cache. Additional configuration `options <http://docs.openstack.org/developer/oslo.cache/opts.html#cache>`_ are also required.


