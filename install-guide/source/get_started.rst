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
  statistics. There may be other types of agents in the future, but
  for now our focus is creating the compute agent.

A central agent (``ceilometer-agent-central``)
  Runs on a central management server to poll for resource utilization
  statistics for resources not tied to instances or compute nodes.
  Multiple agents can be started to scale service horizontally.

A notification agent (``ceilometer-agent-notification``)
  Runs on a central management server(s) and consumes messages from
  the message queue(s) to build event and metering data.

A collector (``ceilometer-collector``)
  Runs on central management server(s) and dispatches collected
  telemetry data to a data store or external consumer without
  modification.

An API server (``ceilometer-api``)
  Runs on one or more central management servers to provide data
  access from the data store.

These services communicate by using the OpenStack messaging bus. Only
the collector and API server have access to the data store.