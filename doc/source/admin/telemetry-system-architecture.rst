.. _telemetry-system-architecture:

===================
System architecture
===================

The Telemetry service uses an agent-based architecture. Several modules
combine their responsibilities to collect, normalize, and redirect data
to be used for use cases such as metering, monitoring, and alerting.

The Telemetry service is built from the following agents:

ceilometer-polling
    Polls for different kinds of meter data by using the polling
    plug-ins (pollsters) registered in different namespaces. It provides a
    single polling interface across different namespaces.

.. note::

   The ``ceilometer-polling`` service provides polling support on any
   namespace but many distributions continue to provide namespace-scoped
   agents: ``ceilometer-agent-central``, ``ceilometer-agent-compute``,
   and ``ceilometer-agent-ipmi``.

ceilometer-agent-notification
    Consumes AMQP messages from other OpenStack services, normalizes messages,
    and publishes them to configured targets.

Except for the ``ceilometer-polling`` agents polling the ``compute`` or
``ipmi`` namespaces, all the other services are placed on one or more
controller nodes.

The Telemetry architecture depends on the AMQP service both for
consuming notifications coming from OpenStack services and internal
communication.


.. _telemetry-supported-databases:

Supported databases
~~~~~~~~~~~~~~~~~~~

The other key external component of Telemetry is the database, where
events, samples, alarm definitions, and alarms are stored. Each of the data
models have their own storage service and each support various back ends.

The list of supported base back ends for measurements:

-  `gnocchi <https://gnocchi.osci.io/>`__

-  `Monasca <https://docs.openstack.org/monasca-api/latest/>`__

The list of supported base back ends for alarms:

-  `MySQL <http://www.mysql.com/>`__

-  `PostgreSQL <http://www.postgresql.org/>`__


The list of supported base back ends for events:

-  `ElasticSearch <https://www.elastic.co/>`__

-  `MongoDB <https://www.mongodb.org/>`__

-  `MySQL <http://www.mysql.com/>`__

-  `PostgreSQL <http://www.postgresql.org/>`__


.. _telemetry-supported-hypervisors:

Supported hypervisors
~~~~~~~~~~~~~~~~~~~~~

The Telemetry service collects information about the virtual machines,
which requires close connection to the hypervisor that runs on the
compute hosts.

The following is a list of supported hypervisors.

-  `Libvirt supported hypervisors <http://libvirt.org/>`__ such as KVM and QEMU
-  `Hyper-V <https://docs.microsoft.com/en-us/windows-server/virtualization/hyper-v/hyper-v-on-windows-server>`__
-  `XEN <http://www.xenproject.org/help/documentation.html>`__
-  `VMware vSphere <https://www.vmware.com/support/vsphere-hypervisor.html>`__

.. note::

   For details about hypervisor support in libvirt please see the
   `Libvirt API support matrix <http://libvirt.org/hvsupport.html>`__.


Supported networking services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry is able to retrieve information from external networking services:

-  SDN controller meters:

   -  `OpenDaylight <https://www.opendaylight.org/>`__
   -  `OpenContrail <http://www.opencontrail.org/>`__
