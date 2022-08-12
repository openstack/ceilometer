.. _telemetry-data-collection:

===============
Data collection
===============

The main responsibility of Telemetry in OpenStack is to collect
information about the system that can be used by billing systems or
interpreted by analytic tooling.

Collected data can be stored in the form of samples or events in the
supported databases, which are listed
in :ref:`telemetry-supported-databases`.

The available data collection mechanisms are:

Notifications
    Processing notifications from other OpenStack services, by consuming
    messages from the configured message queue system.

Polling
    Retrieve information directly from the hypervisor or by using the APIs of
    other OpenStack services.

Notifications
=============

All OpenStack services send notifications about the executed operations
or system state. Several notifications carry information that can be
metered. For example, CPU time of a VM instance created by OpenStack
Compute service.

The notification agent is responsible for consuming notifications. This
component is responsible for consuming from the message bus and transforming
notifications into events and measurement samples.

By default, the notification agent is configured to build both events and
samples. To enable selective data models, set the required pipelines using
`pipelines` option under the `[notification]` section.

Additionally, the notification agent is responsible to send to any supported
publisher target such as gnocchi or panko. These services persist the data in
configured databases.

The different OpenStack services emit several notifications about the
various types of events that happen in the system during normal
operation. Not all these notifications are consumed by the Telemetry
service, as the intention is only to capture the billable events and
notifications that can be used for monitoring or profiling purposes. The
notifications handled are contained under the `ceilometer.sample.endpoint`
namespace.

.. note::

   Some services require additional configuration to emit the
   notifications. Please see the :ref:`install_controller` for more details.

.. _meter_definitions:

Meter definitions
-----------------

The Telemetry service collects a subset of the meters by filtering
notifications emitted by other OpenStack services. You can find the meter
definitions in a separate configuration file, called
``ceilometer/data/meters.d/meters.yaml``. This enables
operators/administrators to add new meters to Telemetry project by updating
the ``meters.yaml`` file without any need for additional code changes.

.. note::

   The ``meters.yaml`` file should be modified with care. Unless intended,
   do not remove any existing meter definitions from the file. Also, the
   collected meters can differ in some cases from what is referenced in the
   documentation.

It also support loading multiple meter definition files and allow users to add
their own meter definitions into several files according to different types of
metrics under the directory of ``/etc/ceilometer/meters.d``.

A standard meter definition looks like:

.. code-block:: yaml

   ---
   metric:
     - name: 'meter name'
       event_type: 'event name'
       type: 'type of meter eg: gauge, cumulative or delta'
       unit: 'name of unit eg: MB'
       volume: 'path to a measurable value eg: $.payload.size'
       resource_id: 'path to resource id eg: $.payload.id'
       project_id: 'path to project id eg: $.payload.owner'
       metadata: 'addiitonal key-value data describing resource'

The definition above shows a simple meter definition with some fields,
from which ``name``, ``event_type``, ``type``, ``unit``, and ``volume``
are required. If there is a match on the event type, samples are generated
for the meter.

The ``meters.yaml`` file contains the sample
definitions for all the meters that Telemetry is collecting from
notifications. The value of each field is specified by using JSON path in
order to find the right value from the notification message. In order to be
able to specify the right field you need to be aware of the format of the
consumed notification. The values that need to be searched in the notification
message are set with a JSON path starting with ``$.`` For instance, if you need
the ``size`` information from the payload you can define it like
``$.payload.size``.

A notification message may contain multiple meters. You can use ``*`` in
the meter definition to capture all the meters and generate samples
respectively. You can use wild cards as shown in the following example:

.. code-block:: yaml

   ---
   metric:
     - name: $.payload.measurements.[*].metric.[*].name
       event_type: 'event_name.*'
       type: 'delta'
       unit: $.payload.measurements.[*].metric.[*].unit
       volume: payload.measurements.[*].result
       resource_id: $.payload.target
       user_id: $.payload.initiator.id
       project_id: $.payload.initiator.project_id

In the above example, the ``name`` field is a JSON path with matching
a list of meter names defined in the notification message.

You can use complex operations on JSON paths. In the following example,
``volume`` and ``resource_id`` fields perform an arithmetic
and string concatenation:

.. code-block:: yaml

   ---
   metric:
   - name: 'compute.node.cpu.idle.percent'
     event_type: 'compute.metrics.update'
     type: 'gauge'
     unit: 'percent'
     volume: payload.metrics[?(@.name='cpu.idle.percent')].value * 100
     resource_id: $.payload.host + "_" + $.payload.nodename

You can use the ``timedelta`` plug-in to evaluate the difference in seconds
between two ``datetime`` fields from one notification.

.. code-block:: yaml

   ---
   metric:
   - name: 'compute.instance.booting.time'
     event_type: 'compute.instance.create.end'
    type: 'gauge'
    unit: 'sec'
    volume:
      fields: [$.payload.created_at, $.payload.launched_at]
      plugin: 'timedelta'
    project_id: $.payload.tenant_id
    resource_id: $.payload.instance_id

.. _Polling-Configuration:

Polling
=======

The Telemetry service is intended to store a complex picture of the
infrastructure. This goal requires additional information than what is
provided by the events and notifications published by each service. Some
information is not emitted directly, like resource usage of the VM
instances.

Therefore Telemetry uses another method to gather this data by polling
the infrastructure including the APIs of the different OpenStack
services and other assets, like hypervisors. The latter case requires
closer interaction with the compute hosts. To solve this issue,
Telemetry uses an agent based architecture to fulfill the requirements
against the data collection.

Configuration
-------------

Polling rules are defined by the `polling.yaml` file. It defines the pollsters
to enable and the interval they should be polled.

Each source configuration encapsulates meter name matching which matches
against the entry point of pollster. It also includes: polling
interval determination, optional resource enumeration or discovery.

All samples generated by polling are placed on the queue to be handled by
the pipeline configuration loaded in the notification agent.

The polling definition may look like the following::

    ---
    sources:
      - name: 'source name'
        interval: 'how often the samples should be generated'
        meters:
          - 'meter filter'
        resources:
          - 'list of resource URLs'
        discovery:
          - 'list of discoverers'

The *interval* parameter in the sources section defines the cadence of sample
generation in seconds.

Polling plugins are invoked according to each source's section whose *meters*
parameter matches the plugin's meter name. Its matching logic functions the
same as pipeline filtering.

The optional *resources* section of a polling source allows a list of
static resource URLs to be configured. An amalgamated list of all
statically defined resources are passed to individual pollsters for polling.

The optional *discovery* section of a polling source contains the list of
discoverers. These discoverers can be used to dynamically discover the
resources to be polled by the pollsters.

If both *resources* and *discovery* are set, the final resources passed to the
pollsters will be the combination of the dynamic resources returned by the
discoverers and the static resources defined in the *resources* section.

Agents
------

There are three types of agents supporting the polling mechanism, the
``compute agent``, the ``central agent``, and the ``IPMI agent``. Under
the hood, all the types of polling agents are the same
``ceilometer-polling`` agent, except that they load different polling
plug-ins (pollsters) from different namespaces to gather data. The following
subsections give further information regarding the architectural and
configuration details of these components.

Running :command:`ceilometer-agent-compute` is exactly the same as:

.. code-block:: console

   $ ceilometer-polling --polling-namespaces compute

Running :command:`ceilometer-agent-central` is exactly the same as:

.. code-block:: console

   $ ceilometer-polling --polling-namespaces central

Running :command:`ceilometer-agent-ipmi` is exactly the same as:

.. code-block:: console

   $ ceilometer-polling --polling-namespaces ipmi

Compute agent
~~~~~~~~~~~~~

This agent is responsible for collecting resource usage data of VM
instances on individual compute nodes within an OpenStack deployment.
This mechanism requires a closer interaction with the hypervisor,
therefore a separate agent type fulfills the collection of the related
meters, which is placed on the host machines to retrieve this
information locally.

A Compute agent instance has to be installed on each and every compute
node, installation instructions can be found in the :ref:`install_compute`
section in the Installation Tutorials and Guides.

The list of supported hypervisors can be found in
:ref:`telemetry-supported-hypervisors`. The Compute agent uses the API of the
hypervisor installed on the compute hosts. Therefore, the supported meters may
be different in case of each virtualization back end, as each inspection tool
provides a different set of meters.

The list of collected meters can be found in :ref:`telemetry-compute-meters`.
The support column provides the information about which meter is available for
each hypervisor supported by the Telemetry service.

Central agent
~~~~~~~~~~~~~

This agent is responsible for polling public REST APIs to retrieve additional
information on OpenStack resources not already surfaced via notifications.

Some of the services polled with this agent are:

-  OpenStack Networking
-  OpenStack Object Storage
-  OpenStack Block Storage

To install and configure this service use the :ref:`install_rdo`
section in the Installation Tutorials and Guides.

Although Ceilometer has a set of default polling agents, operators can
add new pollsters dynamically via the dynamic pollsters subsystem
:ref:`telemetry_dynamic_pollster`.


.. _telemetry-ipmi-agent:

IPMI agent
~~~~~~~~~~

This agent is responsible for collecting IPMI sensor data and Intel Node
Manager data on individual compute nodes within an OpenStack deployment.
This agent requires an IPMI capable node with the ipmitool utility installed,
which is commonly used for IPMI control on various Linux distributions.

An IPMI agent instance could be installed on each and every compute node
with IPMI support, except when the node is managed by the Bare metal
service and the ``conductor.send_sensor_data`` option is set to ``true``
in the Bare metal service. It is no harm to install this agent on a
compute node without IPMI or Intel Node Manager support, as the agent
checks for the hardware and if none is available, returns empty data. It
is suggested that you install the IPMI agent only on an IPMI capable
node for performance reasons.

The list of collected meters can be found in
:ref:`telemetry-bare-metal-service`.

.. note::

   Do not deploy both the IPMI agent and the Bare metal service on one
   compute node. If ``conductor.send_sensor_data`` is set, this
   misconfiguration causes duplicated IPMI sensor samples.
