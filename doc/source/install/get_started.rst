==========================================
Telemetry Data Collection service overview
==========================================

The Telemetry Data Collection services provide the following functions:

* Efficiently polls metering data related to OpenStack services.

* Collects event and metering data by monitoring notifications sent
  from services.

* Publishes collected data to various targets including data stores and
  message queues.

The Telemetry service consists of the following components:

A compute agent (``ceilometer-agent-compute``)
  Runs on each compute node and polls for resource utilization
  statistics. This is actually the polling agent ``ceilometer-polling``
  running with parameter ``--polling-namespace compute``.

A central agent (``ceilometer-agent-central``)
  Runs on a central management server to poll for resource utilization
  statistics for resources not tied to instances or compute nodes.
  Multiple agents can be started to scale service horizontally. This is
  actually the polling agent ``ceilometer-polling`` running with
  parameter ``--polling-namespace central``.

A notification agent (``ceilometer-agent-notification``)
  Runs on a central management server(s) and consumes messages from
  the message queue(s) to build event and metering data. Data is then
  published to defined targets. By default, data is pushed to Gnocchi_.

These services communicate by using the OpenStack messaging bus. Ceilometer
data is designed to be published to various endpoints for storage and
analysis.

.. note::

   Ceilometer previously provided a storage and API solution. As of Newton,
   this functionality is officially deprecated and discouraged. For efficient
   storage and statistical analysis of Ceilometer data, Gnocchi_ is
   recommended.

.. _Gnocchi: https://gnocchi.osci.io
