====================
Newton Release Notes
====================

7.0.5
=====

Bug Fixes
---------

.. releasenotes/notes/refresh-legacy-cache-e4dbbd3e2eeca70b.yaml @ 66dd8ab65e2d9352de86e47056dea0b701e21a15

- A local cache is used when polling instance metrics to minimise calls Nova
  API. A new option is added `resource_cache_expiry` to configure a time to
  live for cache before it expires. This resolves issue where migrated
  instances are not removed from cache.


7.0.1
=====

New Features
------------

.. releasenotes/notes/http_proxy_to_wsgi_enabled-616fa123809e1600.yaml @ 032032642ad49e01d706f19f51d672fcff403442

- Ceilometer sets up the HTTPProxyToWSGI middleware in front of Ceilometer. The purpose of this middleware is to set up the request URL correctly in case there is a proxy (for instance, a loadbalancer such as HAProxy) in front of Ceilometer. So, for instance, when TLS connections are being terminated in the proxy, and one tries to get the versions from the / resource of Ceilometer, one will notice that the protocol is incorrect; It will show 'http' instead of 'https'. So this middleware handles such cases. Thus helping Keystone discovery work correctly. The HTTPProxyToWSGI is off by default and needs to be enabled via a configuration value.


7.0.0
=====

Prelude
-------

.. releasenotes/notes/rename-ceilometer-dbsync-eb7a1fa503085528.yaml @ 18c181f0b3ce07a0cd552a9060dd09a95cc26078

Ceilometer backends are no more only databases but also REST API like Gnocchi. So ceilometer-dbsync binary name doesn't make a lot of sense and have been renamed ceilometer-upgrade. The new binary handles database schema upgrade like ceilometer-dbsync does, but it also handle any changes needed in configured ceilometer backends like Gnocchi.


New Features
------------

.. releasenotes/notes/add-magnum-event-4c75ed0bb268d19c.yaml @ cf3f7c992e0d29e06a7bff6c1df2f0144418d80f

- Added support for magnum bay CRUD events, event_type is 'magnum.bay.*'.

.. releasenotes/notes/http-dispatcher-verify-ssl-551d639f37849c6f.yaml @ 2fca7ebd7c6a4d29c8a320fffd035ed9814e8293

- In the [dispatcher_http] section of ceilometer.conf, verify_ssl can be set to True to use system-installed certificates (default value) or False to ignore certificate verification (use in development only!). verify_ssl can also be set to the location of a certificate file e.g. /some/path/cert.crt (use for self-signed certs) or to a directory of certificates. The value is passed as the 'verify' option to the underlying requests method, which is documented at http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification

.. releasenotes/notes/memory-bandwidth-meter-f86cf01178573671.yaml @ ed7b6dbc952e49ca69de9a94a01398b106aece4b

- Add two new meters, including memory.bandwidth.total and memory.bandwidth.local, to get memory bandwidth statistics based on Intel CMT feature.

.. releasenotes/notes/perf-events-meter-b06c2a915c33bfaf.yaml @ aaedbbe0eb02ad1f86395a5a490495b64ce26777

- Add four new meters, including perf.cpu.cycles for the number of cpu cycles one instruction needs, perf.instructions for the count of instructions, perf.cache_references for the count of cache hits and cache_misses for the count of caches misses.

.. releasenotes/notes/support-meter-batch-recording-mongo-6c2bdf4fbb9764eb.yaml @ a2a04e5d234ba358c25d541f31f8ca1a61bfd5d8

- Add support of batch recording metering data to mongodb backend, since the pymongo support *insert_many* interface which can be used to batch record items, in "big-data" scenarios, this change can improve the performance of metering data recording.

.. releasenotes/notes/use-glance-v2-in-image-pollsters-137a315577d5dc4c.yaml @ f8933f4abda4ecfc07ee41f84fd5fd8f6667e95a

- Since the Glance v1 APIs won't be maintained any more, this change add the support of glance v2 in images pollsters.


Upgrade Notes
-------------

.. releasenotes/notes/always-requeue-7a2df9243987ab67.yaml @ 40684dafae76eab77b66bb1da7e143a3d7e2c9c8

- The options 'requeue_event_on_dispatcher_error' and 'requeue_sample_on_dispatcher_error' have been enabled and removed.

.. releasenotes/notes/single-thread-pipelines-f9e6ac4b062747fe.yaml @ 5750fddf288c749cacfc825753928f66e755758d

- Batching is enabled by default now when coordinated workers are enabled. Depending on load, it is recommended to scale out the number of `pipeline_processing_queues` to improve distribution. `batch_size` should also be configured accordingly.

.. releasenotes/notes/use-glance-v2-in-image-pollsters-137a315577d5dc4c.yaml @ f8933f4abda4ecfc07ee41f84fd5fd8f6667e95a

- The option 'glance_page_size' has been removed because it's not actually needed.


Deprecation Notes
-----------------

.. releasenotes/notes/deprecated_database_event_dispatcher_panko-607d558c86a90f17.yaml @ 3685dcf417543db0bb708b347e996d88385c8c5b

- The event database dispatcher is now deprecated. It has been moved to a new project, alongside the Ceilometer API for /v2/events, called Panko.

.. releasenotes/notes/kwapi_deprecated-c92b9e72c78365f0.yaml @ 2bb81d41f1c5086b68b1290362c72966c1e33702

- The Kwapi pollsters are deprecated and will be removed in the next major version of Ceilometer.

.. releasenotes/notes/rename-ceilometer-dbsync-eb7a1fa503085528.yaml @ 18c181f0b3ce07a0cd552a9060dd09a95cc26078

- For backward compatibility reason we temporary keep ceilometer-dbsync, at least for one major version to ensure deployer have time update their tooling.


Critical Issues
---------------

.. releasenotes/notes/always-requeue-7a2df9243987ab67.yaml @ 40684dafae76eab77b66bb1da7e143a3d7e2c9c8

- The previous configuration options default for 'requeue_sample_on_dispatcher_error' and 'requeue_event_on_dispatcher_error' allowed to lose data very easily: if the dispatcher failed to send data to the backend (e.g. Gnocchi is down), then the dispatcher raised and the data were lost forever. This was completely unacceptable, and nobody should be able to configure Ceilometer in that way."


Bug Fixes
---------

.. releasenotes/notes/add-db-legacy-clean-tool-7b3e3714f414c448.yaml @ 800034dc0bbb9502893dedd9bcde7c170780c375

- [`bug 1578128 <https://bugs.launchpad.net/ceilometer/+bug/1578128>`_] Add a tool that allow users to drop the legacy alarm and alarm_history tables.

.. releasenotes/notes/add-full-snmpv3-usm-support-ab540c902fa89b9d.yaml @ dc254e2f78a4bb42b0df6556df8347c7137ab5b2

- [`bug 1597618 <https://bugs.launchpad.net/ceilometer/+bug/1597618>`_] Add the full support of snmp v3 user security model.

.. releasenotes/notes/single-thread-pipelines-f9e6ac4b062747fe.yaml @ 5750fddf288c749cacfc825753928f66e755758d

- Fix to improve handling messages in environments heavily backed up. Previously, notification handlers greedily grabbed messages from queues which could cause ordering issues. A fix was applied to sequentially process messages in a single thread to prevent ordering issues.

.. releasenotes/notes/unify-timestamp-of-polled-data-fbfcff43cd2d04bc.yaml @ 8dd821a03dcff45258251bebfd2beb86c07d94f7

- [`bug 1491509 <https://bugs.launchpad.net/ceilometer/+bug/1491509>`_] Patch to unify timestamp in samples polled by pollsters. Set the time point polling starts as timestamp of samples, and drop timetamping in pollsters.


