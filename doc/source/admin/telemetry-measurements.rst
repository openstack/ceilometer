.. _telemetry-measurements:

============
Measurements
============

The Telemetry service collects meters within an OpenStack deployment.
This section provides a brief summary about meters format and origin and
also contains the list of available meters.

Telemetry collects meters by polling the infrastructure elements and
also by consuming the notifications emitted by other OpenStack services.
For more information about the polling mechanism and notifications see
:ref:`telemetry-data-collection`. There are several meters which are collected
by polling and by consuming. The origin for each meter is listed in the tables
below.

.. note::

   You may need to configure Telemetry or other OpenStack services in
   order to be able to collect all the samples you need. For further
   information about configuration requirements see the `Telemetry chapter
   <https://docs.openstack.org/ceilometer/latest/install/index.html>`__
   in the Installation Tutorials and Guides.

Telemetry uses the following meter types:

+--------------+--------------------------------------------------------------+
| Type         | Description                                                  |
+==============+==============================================================+
| Cumulative   | Increasing over time (instance hours)                        |
+--------------+--------------------------------------------------------------+
| Delta        | Changing over time (bandwidth)                               |
+--------------+--------------------------------------------------------------+
| Gauge        | Discrete items (floating IPs, image uploads) and fluctuating |
|              | values (disk I/O)                                            |
+--------------+--------------------------------------------------------------+

|

Telemetry provides the possibility to store metadata for samples. This
metadata can be extended for OpenStack Compute and OpenStack Object
Storage.

In order to add additional metadata information to OpenStack Compute you
have two options to choose from. The first one is to specify them when
you boot up a new instance. The additional information will be stored
with the sample in the form of ``resource_metadata.user_metadata.*``.
The new field should be defined by using the prefix ``metering.``. The
modified boot command look like the following:

.. code-block:: console

   $ openstack server create --property metering.custom_metadata=a_value my_vm

The other option is to set the ``reserved_metadata_keys`` to the list of
metadata keys that you would like to be included in
``resource_metadata`` of the instance related samples that are collected
for OpenStack Compute. This option is included in the ``DEFAULT``
section of the ``ceilometer.conf`` configuration file.

You might also specify headers whose values will be stored along with
the sample data of OpenStack Object Storage. The additional information
is also stored under ``resource_metadata``. The format of the new field
is ``resource_metadata.http_header_$name``, where ``$name`` is the name of
the header with ``-`` replaced by ``_``.

For specifying the new header, you need to set ``metadata_headers`` option
under the ``[filter:ceilometer]`` section in ``proxy-server.conf`` under the
``swift`` folder. You can use this additional data for instance to distinguish
external and internal users.

Measurements are grouped by services which are polled by
Telemetry or emit notifications that this service consumes.

.. _telemetry-compute-meters:

OpenStack Compute
~~~~~~~~~~~~~~~~~

The following meters are collected for OpenStack Compute.

+-----------+-------+------+----------+----------+---------+------------------+
| Name      | Type  | Unit | Resource | Origin   | Support | Note             |
+===========+=======+======+==========+==========+=========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+-----------+-------+------+----------+----------+---------+------------------+
| memory    | Gauge | MB   | instance | Notific\ | Libvirt,| Volume of RAM    |
|           |       |      | ID       | ation    | Hyper-V | allocated to the |
|           |       |      |          |          |         | instance         |
+-----------+-------+------+----------+----------+---------+------------------+
| memory.\  | Gauge | MB   | instance | Pollster | Libvirt,| Volume of RAM    |
| usage     |       |      | ID       |          | Hyper-V,| used by the inst\|
|           |       |      |          |          | vSphere,| ance from the    |
|           |       |      |          |          | XenAPI  | amount of its    |
|           |       |      |          |          |         | allocated memory |
+-----------+-------+------+----------+----------+---------+------------------+
| memory.r\ | Gauge | MB   | instance | Pollster | Libvirt | Volume of RAM u\ |
| esident   |       |      | ID       |          |         | sed by the inst\ |
|           |       |      |          |          |         | ance on the phy\ |
|           |       |      |          |          |         | sical machine    |
+-----------+-------+------+----------+----------+---------+------------------+
| cpu       | Cumu\ | ns   | instance | Pollster | Libvirt,| CPU time used    |
|           | lative|      | ID       |          | Hyper-V |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| cpu.delta | Delta | ns   | instance | Pollster | Libvirt,| CPU time used s\ |
|           |       |      | ID       |          | Hyper-V | ince previous d\ |
|           |       |      |          |          |         | atapoint         |
+-----------+-------+------+----------+----------+---------+------------------+
| cpu_util  | Gauge | %    | instance | Pollster | LibVirt,| Average CPU      |
|           |       |      | ID       |          | vSphere,| utilization      |
|           |       |      |          |          | XenAPI  |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| vcpus     | Gauge | vcpu | instance | Notific\ | Libvirt,| Number of virtual|
|           |       |      | ID       | ation    | Hyper-V | CPUs allocated to|
|           |       |      |          |          |         | the instance     |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.read\| Cumul\| req\ | instance | Pollster | Libvirt,| Number of read   |
| .requests | ative | uest | ID       |          | Hyper-V | requests         |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.read\| Gauge | requ\| instance | Pollster | Libvirt,| Average rate of  |
| .requests\|       | est/s| ID       |          | Hyper-V,| read requests    |
| .rate     |       |      |          |          | vSphere |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.writ\| Cumul\| req\ | instance | Pollster | Libvirt,| Number of write  |
| e.requests| ative | uest | ID       |          | Hyper-V | requests         |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.writ\| Gauge | requ\| instance | Pollster | Libvirt,| Average rate of  |
| e.request\|       | est/s| ID       |          | Hyper-V,| write requests   |
| s.rate    |       |      |          |          | vSphere |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.read\| Cumu\ | B    | instance | Pollster | Libvirt,| Volume of reads  |
| .bytes    | lative|      | ID       |          | Hyper-V |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.read\| Gauge | B/s  | instance | Pollster | Libvirt,| Average rate of  |
| .bytes.\  |       |      | ID       |          | Hyper-V,| reads            |
| rate      |       |      |          |          | vSphere,|                  |
|           |       |      |          |          | XenAPI  |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.writ\| Cumu\ | B    | instance | Pollster | Libvirt,| Volume of writes |
| e.bytes   | lative|      | ID       |          | Hyper-V |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.writ\| Gauge | B/s  | instance | Pollster | Libvirt,| Average rate of  |
| e.bytes.\ |       |      | ID       |          | Hyper-V,| writes           |
| rate      |       |      |          |          | vSphere,|                  |
|           |       |      |          |          | XenAPI  |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Cumu\ | req\ | disk ID  | Pollster | Libvirt,| Number of read   |
| ice.read\ | lative| uest |          |          | Hyper-V | requests         |
| .requests |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | requ\| disk ID  | Pollster | Libvirt,| Average rate of  |
| ice.read\ |       | est/s|          |          | Hyper-V,| read requests    |
| .requests\|       |      |          |          | vSphere |                  |
| .rate     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Cumu\ | req\ | disk ID  | Pollster | Libvirt,| Number of write  |
| ice.write\| lative| uest |          |          | Hyper-V | requests         |
| .requests |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | requ\| disk ID  | Pollster | Libvirt,| Average rate of  |
| ice.write\|       | est/s|          |          | Hyper-V,| write requests   |
| .requests\|       |      |          |          | vSphere |                  |
| .rate     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Cumu\ | B    | disk ID  | Pollster | Libvirt,| Volume of reads  |
| ice.read\ | lative|      |          |          | Hyper-V |                  |
| .bytes    |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | B/s  | disk ID  | Pollster | Libvirt,| Average rate of  |
| ice.read\ |       |      |          |          | Hyper-V,| reads            |
| .bytes    |       |      |          |          | vSphere |                  |
| .rate     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Cumu\ | B    | disk ID  | Pollster | Libvirt,| Volume of writes |
| ice.write\| lative|      |          |          | Hyper-V |                  |
| .bytes    |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | B/s  | disk ID  | Pollster | Libvirt,| Average rate of  |
| ice.write\|       |      |          |          | Hyper-V,| writes           |
| .bytes    |       |      |          |          | vSphere |                  |
| .rate     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.root\| Gauge | GB   | instance | Notific\ | Libvirt,| Size of root disk|
| .size     |       |      | ID       | ation    | Hyper-V |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.ephe\| Gauge | GB   | instance | Notific\ | Libvirt,| Size of ephemeral|
| meral.size|       |      | ID       | ation    | Hyper-V | disk             |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.lat\ | Gauge | ms   | instance | Pollster | Hyper-V | Average disk la\ |
| ency      |       |      | ID       |          |         | tency            |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.iop\ | Gauge | coun\| instance | Pollster | Hyper-V | Average disk io\ |
| s         |       | t/s  | ID       |          |         | ps               |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | ms   | disk ID  | Pollster | Hyper-V | Average disk la\ |
| ice.late\ |       |      |          |          |         | tency per device |
| ncy       |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | coun\| disk ID  | Pollster | Hyper-V | Average disk io\ |
| ice.iops  |       | t/s  |          |          |         | ps per device    |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.cap\ | Gauge | B    | instance | Pollster | Libvirt | The amount of d\ |
| acity     |       |      | ID       |          |         | isk that the in\ |
|           |       |      |          |          |         | stance can see   |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.all\ | Gauge | B    | instance | Pollster | Libvirt | The amount of d\ |
| ocation   |       |      | ID       |          |         | isk occupied by  |
|           |       |      |          |          |         | the instance o\  |
|           |       |      |          |          |         | n the host mach\ |
|           |       |      |          |          |         | ine              |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.usa\ | Gauge | B    | instance | Pollster | Libvirt | The physical si\ |
| ge        |       |      | ID       |          |         | ze in bytes of   |
|           |       |      |          |          |         | the image conta\ |
|           |       |      |          |          |         | iner on the host |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | B    | disk ID  | Pollster | Libvirt | The amount of d\ |
| ice.capa\ |       |      |          |          |         | isk per device   |
| city      |       |      |          |          |         | that the instan\ |
|           |       |      |          |          |         | ce can see       |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | B    | disk ID  | Pollster | Libvirt | The amount of d\ |
| ice.allo\ |       |      |          |          |         | isk per device   |
| cation    |       |      |          |          |         | occupied by the  |
|           |       |      |          |          |         | instance on th\  |
|           |       |      |          |          |         | e host machine   |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.dev\ | Gauge | B    | disk ID  | Pollster | Libvirt | The physical si\ |
| ice.usag\ |       |      |          |          |         | ze in bytes of   |
| e         |       |      |          |          |         | the image conta\ |
|           |       |      |          |          |         | iner on the hos\ |
|           |       |      |          |          |         | t per device     |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumu\ | B    | interface| Pollster | Libvirt,| Number of        |
| incoming.\| lative|      | ID       |          | Hyper-V | incoming bytes   |
| bytes     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Gauge | B/s  | interface| Pollster | Libvirt,| Average rate of  |
| incoming.\|       |      | ID       |          | Hyper-V,| incoming bytes   |
| bytes.rate|       |      |          |          | vSphere,|                  |
|           |       |      |          |          | XenAPI  |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumu\ | B    | interface| Pollster | Libvirt,| Number of        |
| outgoing\ | lative|      | ID       |          | Hyper-V | outgoing bytes   |
| .bytes    |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Gauge | B/s  | interface| Pollster | Libvirt,| Average rate of  |
| outgoing.\|       |      | ID       |          | Hyper-V,| outgoing bytes   |
| bytes.rate|       |      |          |          | vSphere,|                  |
|           |       |      |          |          | XenAPI  |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumu\ | pac\ | interface| Pollster | Libvirt,| Number of        |
| incoming\ | lative| ket  | ID       |          | Hyper-V | incoming packets |
| .packets  |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Gauge | pack\| interface| Pollster | Libvirt,| Average rate of  |
| incoming\ |       | et/s | ID       |          | Hyper-V,| incoming packets |
| .packets\ |       |      |          |          | vSphere,|                  |
| .rate     |       |      |          |          | XenAPI  |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumu\ | pac\ | interface| Pollster | Libvirt,| Number of        |
| outgoing\ | lative| ket  | ID       |          | Hyper-V | outgoing packets |
| .packets  |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Gauge | pac\ | interface| Pollster | Libvirt,| Average rate of  |
| outgoing\ |       | ket/s| ID       |          | Hyper-V,| outgoing packets |
| .packets\ |       |      |          |          | vSphere,|                  |
| .rate     |       |      |          |          | XenAPI  |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| **Meters added in the Newton release**                                      |
+-----------+-------+------+----------+----------+---------+------------------+
| cpu_l3_c\ | Gauge | B    | instance | Pollster | Libvirt | L3 cache used b\ |
| ache      |       |      | ID       |          |         | y the instance   |
+-----------+-------+------+----------+----------+---------+------------------+
| memory.b\ | Gauge | B/s  | instance | Pollster | Libvirt | Total system ba\ |
| andwidth\ |       |      | ID       |          |         | ndwidth from on\ |
| .total    |       |      |          |          |         | e level of cache |
+-----------+-------+------+----------+----------+---------+------------------+
| memory.b\ | Gauge | B/s  | instance | Pollster | Libvirt | Bandwidth of me\ |
| andwidth\ |       |      | ID       |          |         | mory traffic fo\ |
| .local    |       |      |          |          |         | r a memory cont\ |
|           |       |      |          |          |         | roller           |
+-----------+-------+------+----------+----------+---------+------------------+
| perf.cpu\ | Gauge | cyc\ | instance | Pollster | Libvirt | the number of c\ |
| .cycles   |       | le   | ID       |          |         | pu cycles one i\ |
|           |       |      |          |          |         | nstruction needs |
+-----------+-------+------+----------+----------+---------+------------------+
| perf.ins\ | Gauge | inst\| instance | Pollster | Libvirt | the count of in\ |
| tructions |       | ruct\| ID       |          |         | structions       |
|           |       | ion  |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| perf.cac\ | Gauge | cou\ | instance | Pollster | Libvirt | the count of ca\ |
| he.refer\ |       | nt   | ID       |          |         | che hits         |
| ences     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| perf.cac\ | Gauge | cou\ | instance | Pollster | Libvirt | the count of ca\ |
| he.misses |       | nt   | ID       |          |         | che misses       |
+-----------+-------+------+----------+----------+---------+------------------+
| **Meters added in the Ocata release**                                       |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumul\| pack\| interface| Pollster | Libvirt | Number of        |
| incoming\ | ative | et   | ID       |          |         | incoming dropped |
| .packets\ |       |      |          |          |         | packets          |
| .drop     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumul\| pack\| interface| Pollster | Libvirt | Number of        |
| outgoing\ | ative | et   | ID       |          |         | outgoing dropped |
| .packets\ |       |      |          |          |         | packets          |
| .drop     |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumul\| pack\| interface| Pollster | Libvirt | Number of        |
| incoming\ | ative | et   | ID       |          |         | incoming error   |
| .packets\ |       |      |          |          |         | packets          |
| .error    |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| network.\ | Cumul\| pack\| interface| Pollster | Libvirt | Number of        |
| outgoing\ | ative | et   | ID       |          |         | outgoing error   |
| .packets\ |       |      |          |          |         | packets          |
| .error    |       |      |          |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| **Meters added in the Pike release**                                        |
+-----------+-------+------+----------+----------+---------+------------------+
| memory.\  | Cumul\|      |          |          |         |                  |
| swap.in   | ative | MB   | instance | Pollster | Libvirt | Memory swap in   |
|           |       |      | ID       |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| memory.\  | Cumul\|      |          |          |         |                  |
| swap.out  | ative | MB   | instance | Pollster | Libvirt | Memory swap out  |
|           |       |      | ID       |          |         |                  |
+-----------+-------+------+----------+----------+---------+------------------+
| **Meters added in the Queens release**                                      |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.devi\| Cumul\|      |          |          |         | Total time read  |
| ce.read.l\| ative | ns   | Disk ID  | Pollster | Libvirt | operations have  |
| atency    |       |      |          |          |         | taken            |
+-----------+-------+------+----------+----------+---------+------------------+
| disk.devi\| Cumul\|      |          |          |         | Total time write |
| ce.write.\| ative | ns   | Disk ID  | Pollster | Libvirt | operations have  |
| latency   |       |      |          |          |         | taken            |
+-----------+-------+------+----------+----------+---------+------------------+

.. note::

    To enable the libvirt ``memory.usage`` support, you need to install
    libvirt version 1.1.1+, QEMU version 1.5+, and you also need to
    prepare suitable balloon driver in the image. It is applicable
    particularly for Windows guests, most modern Linux distributions
    already have it built in. Telemetry is not able to fetch the
    ``memory.usage`` samples without the image balloon driver.

.. note::

    To enable libvirt ``disk.*`` support when running on RBD-backed shared
    storage, you need to install libvirt version 1.2.16+.

The Telemetry service supports creating new meters by using transformers, but
this is deprecated and discouraged to use. Among the meters gathered from
libvirt and Hyper-V, there are a few which are derived from other meters. The
list of meters that are created by using the ``rate_of_change`` transformer
from the above table is the following:

-  cpu_util

-  cpu.delta

-  disk.read.requests.rate

-  disk.write.requests.rate

-  disk.read.bytes.rate

-  disk.write.bytes.rate

-  disk.device.read.requests.rate

-  disk.device.write.requests.rate

-  disk.device.read.bytes.rate

-  disk.device.write.bytes.rate

-  network.incoming.bytes.rate

-  network.outgoing.bytes.rate

-  network.incoming.packets.rate

-  network.outgoing.packets.rate

.. note::

    If storing data in Gnocchi, derived rate_of_change metrics are also
    computed using Gnocchi in addition to Ceilometer transformers. It avoids
    missing data when Ceilometer services restart.
    To minimize Ceilometer memory requirements transformers can be disabled.
    These ``rate_of_change`` meters are deprecated and will be removed in
    default Ceilometer configuration in future release.


OpenStack Compute is capable of collecting ``CPU`` related meters from
the compute host machines. In order to use that you need to set the
``compute_monitors`` option to ``cpu.virt_driver`` in the
``nova.conf`` configuration file. For further information see the
Compute configuration section in the `Compute chapter
<https://docs.openstack.org/nova/latest/configuration/config.html>`__
of the OpenStack Configuration Reference.

The following host machine related meters are collected for OpenStack
Compute:

+---------------------+-------+------+----------+-------------+---------------+
| Name                | Type  | Unit | Resource | Origin      | Note          |
+=====================+=======+======+==========+=============+===============+
| **Meters added in the Mitaka release or earlier**                           |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Gauge | MHz  | host ID  | Notification| CPU frequency |
| frequency           |       |      |          |             |               |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Cumu\ | ns   | host ID  | Notification| CPU kernel    |
| kernel.time         | lative|      |          |             | time          |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Cumu\ | ns   | host ID  | Notification| CPU idle time |
| idle.time           | lative|      |          |             |               |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Cumu\ | ns   | host ID  | Notification| CPU user mode |
| user.time           | lative|      |          |             | time          |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Cumu\ | ns   | host ID  | Notification| CPU I/O wait  |
| iowait.time         | lative|      |          |             | time          |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Gauge | %    | host ID  | Notification| CPU kernel    |
| kernel.percent      |       |      |          |             | percentage    |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Gauge | %    | host ID  | Notification| CPU idle      |
| idle.percent        |       |      |          |             | percentage    |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Gauge | %    | host ID  | Notification| CPU user mode |
| user.percent        |       |      |          |             | percentage    |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Gauge | %    | host ID  | Notification| CPU I/O wait  |
| iowait.percent      |       |      |          |             | percentage    |
+---------------------+-------+------+----------+-------------+---------------+
| compute.node.cpu.\  | Gauge | %    | host ID  | Notification| CPU           |
| percent             |       |      |          |             | utilization   |
+---------------------+-------+------+----------+-------------+---------------+

.. _telemetry-bare-metal-service:

IPMI meters
~~~~~~~~~~~

Telemetry captures notifications that are emitted by the Bare metal
service. The source of the notifications are IPMI sensors that collect
data from the host machine.

Alternatively, IPMI meters can be generated by deploying the
ceilometer-agent-ipmi on each IPMI-capable node. For further information about
the IPMI agent see :ref:`telemetry-ipmi-agent`.

.. warning::

   To avoid duplication of metering data and unnecessary load on the
   IPMI interface, do not deploy the IPMI agent on nodes that are
   managed by the Bare metal service and keep the
   ``conductor.send_sensor_data`` option set to ``False`` in the
   ``ironic.conf`` configuration file.


The following IPMI sensor meters are recorded:

+------------------+-------+------+----------+-------------+------------------+
| Name             | Type  | Unit | Resource | Origin      | Note             |
+==================+=======+======+==========+=============+==================+
| **Meters added in the Mitaka release or earlier**                           |
+------------------+-------+------+----------+-------------+------------------+
| hardware.ipmi.fan| Gauge | RPM  | fan      | Notificatio\| Fan rounds per   |
|                  |       |      | sensor   | n, Pollster | minute (RPM)     |
+------------------+-------+------+----------+-------------+------------------+
| hardware.ipmi\   | Gauge | C    | temper\  | Notificatio\| Temperature read\|
| .temperature     |       |      | ature    | n, Pollster | ing from sensor  |
|                  |       |      | sensor   |             |                  |
+------------------+-------+------+----------+-------------+------------------+
| hardware.ipmi\   | Gauge | W    | current  | Notificatio\| Current reading  |
| .current         |       |      | sensor   | n, Pollster | from sensor      |
+------------------+-------+------+----------+-------------+------------------+
| hardware.ipmi\   | Gauge | V    | voltage  | Notificatio\| Voltage reading  |
| .voltage         |       |      | sensor   | n, Pollster | from sensor      |
+------------------+-------+------+----------+-------------+------------------+

.. note::

   The sensor data is not available in the Bare metal service by
   default. To enable the meters and configure this module to emit
   notifications about the measured values see the `Installation
   Guide <https://docs.openstack.org/ironic/latest/install/index.html>`__
   for the Bare metal service.


Besides generic IPMI sensor data, the following Intel Node Manager
meters are recorded from capable platform:

+---------------------+-------+------+----------+----------+------------------+
| Name                | Type  | Unit | Resource | Origin   | Note             |
+=====================+=======+======+==========+==========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | W    | host ID  | Pollster | Current power    |
| .power              |       |      |          |          | of the system    |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | C    | host ID  | Pollster | Current tempera\ |
| .temperature        |       |      |          |          | ture of the      |
|                     |       |      |          |          | system           |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | C    | host ID  | Pollster | Inlet temperatu\ |
| .inlet_temperature  |       |      |          |          | re of the system |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | C    | host ID  | Pollster | Outlet temperat\ |
| .outlet_temperature |       |      |          |          | ure of the system|
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | CFM  | host ID  | Pollster | Volumetric airf\ |
| .airflow            |       |      |          |          | low of the syst\ |
|                     |       |      |          |          | em, expressed as |
|                     |       |      |          |          | 1/10th of CFM    |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | CUPS | host ID  | Pollster | CUPS(Compute Us\ |
| .cups               |       |      |          |          | age Per Second)  |
|                     |       |      |          |          | index data of the|
|                     |       |      |          |          | system           |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | %    | host ID  | Pollster | CPU CUPS utiliz\ |
| .cpu_util           |       |      |          |          | ation of the     |
|                     |       |      |          |          | system           |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | %    | host ID  | Pollster | Memory CUPS      |
| .mem_util           |       |      |          |          | utilization of   |
|                     |       |      |          |          | the system       |
+---------------------+-------+------+----------+----------+------------------+
| hardware.ipmi.node\ | Gauge | %    | host ID  | Pollster | IO CUPS          |
| .io_util            |       |      |          |          | utilization of   |
|                     |       |      |          |          | the system       |
+---------------------+-------+------+----------+----------+------------------+

SNMP based meters
~~~~~~~~~~~~~~~~~

Telemetry supports gathering SNMP based generic host meters. In order to
be able to collect this data you need to run snmpd on each target host.

The following meters are available about the host machines by using
SNMP:

+---------------------+-------+------+----------+----------+------------------+
| Name                | Type  | Unit | Resource | Origin   | Note             |
+=====================+=======+======+==========+==========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+---------------------+-------+------+----------+----------+------------------+
| hardware.cpu.load.\ | Gauge | proc\| host ID  | Pollster | CPU load in the  |
| 1min                |       | ess  |          |          | past 1 minute    |
+---------------------+-------+------+----------+----------+------------------+
| hardware.cpu.load.\ | Gauge | proc\| host ID  | Pollster | CPU load in the  |
| 5min                |       | ess  |          |          | past 5 minutes   |
+---------------------+-------+------+----------+----------+------------------+
| hardware.cpu.load.\ | Gauge | proc\| host ID  | Pollster | CPU load in the  |
| 15min               |       | ess  |          |          | past 15 minutes  |
+---------------------+-------+------+----------+----------+------------------+
| hardware.cpu.util   | Gauge | %    | host ID  | Pollster | cpu usage        |
|                     |       |      |          |          | percentage       |
+---------------------+-------+------+----------+----------+------------------+
| hardware.disk.size\ | Gauge | KB   | disk ID  | Pollster | Total disk size  |
| .total              |       |      |          |          |                  |
+---------------------+-------+------+----------+----------+------------------+
| hardware.disk.size\ | Gauge | KB   | disk ID  | Pollster | Used disk size   |
| .used               |       |      |          |          |                  |
+---------------------+-------+------+----------+----------+------------------+
| hardware.memory.to\ | Gauge | KB   | host ID  | Pollster | Total physical   |
| tal                 |       |      |          |          | memory size      |
+---------------------+-------+------+----------+----------+------------------+
| hardware.memory.us\ | Gauge | KB   | host ID  | Pollster | Used physical m\ |
| ed                  |       |      |          |          | emory size       |
+---------------------+-------+------+----------+----------+------------------+
| hardware.memory.bu\ | Gauge | KB   | host ID  | Pollster | Physical memory  |
| ffer                |       |      |          |          | buffer size      |
+---------------------+-------+------+----------+----------+------------------+
| hardware.memory.ca\ | Gauge | KB   | host ID  | Pollster | Cached physical  |
| ched                |       |      |          |          | memory size      |
+---------------------+-------+------+----------+----------+------------------+
| hardware.memory.sw\ | Gauge | KB   | host ID  | Pollster | Total swap space |
| ap.total            |       |      |          |          | size             |
+---------------------+-------+------+----------+----------+------------------+
| hardware.memory.sw\ | Gauge | KB   | host ID  | Pollster | Available swap   |
| ap.avail            |       |      |          |          | space size       |
+---------------------+-------+------+----------+----------+------------------+
| hardware.network.i\ | Cumul\| B    | interface| Pollster | Bytes received   |
| ncoming.bytes       | ative |      | ID       |          | by network inte\ |
|                     |       |      |          |          | rface            |
+---------------------+-------+------+----------+----------+------------------+
| hardware.network.o\ | Cumul\| B    | interface| Pollster | Bytes sent by n\ |
| utgoing.bytes       | ative |      | ID       |          | etwork interface |
+---------------------+-------+------+----------+----------+------------------+
| hardware.network.o\ | Cumul\| pack\| interface| Pollster | Sending error o\ |
| utgoing.errors      | ative | et   | ID       |          | f network inter\ |
|                     |       |      |          |          | face             |
+---------------------+-------+------+----------+----------+------------------+
| hardware.network.i\ | Cumul\| data\| host ID  | Pollster | Number of recei\ |
| p.incoming.datagra\ | ative | grams|          |          | ved datagrams    |
| ms                  |       |      |          |          |                  |
+---------------------+-------+------+----------+----------+------------------+
| hardware.network.i\ | Cumul\| data\| host ID  | Pollster | Number of sent   |
| p.outgoing.datagra\ | ative | grams|          |          | datagrams        |
| ms                  |       |      |          |          |                  |
+---------------------+-------+------+----------+----------+------------------+
| hardware.system_st\ | Cumul\| bloc\| host ID  | Pollster | Aggregated numb\ |
| ats.io.incoming.bl\ | ative | ks   |          |          | er of blocks re\ |
| ocks                |       |      |          |          | ceived to block  |
|                     |       |      |          |          | device           |
+---------------------+-------+------+----------+----------+------------------+
| hardware.system_st\ | Cumul\| bloc\| host ID  | Pollster | Aggregated numb\ |
| ats.io.outgoing.bl\ | ative | ks   |          |          | er of blocks se\ |
| ocks                |       |      |          |          | nt to block dev\ |
|                     |       |      |          |          | ice              |
+---------------------+-------+------+----------+----------+------------------+
| hardware.system_st\ | Gauge | %    | host ID  | Pollster | CPU idle percen\ |
| ats.cpu.idle        |       |      |          |          | tage             |
+---------------------+-------+------+----------+----------+------------------+
| **Meters added in the Queens release**                                      |
+---------------------+-------+------+----------+----------+------------------+
| hardware.disk.read.\| Gauge | B    | disk ID  | Pollster | Bytes read from  |
| bytes               |       |      |          |          | device since boot|
+---------------------+-------+------+----------+----------+------------------+
| hardware.disk.write\| Gauge | B    | disk ID  | Pollster | Bytes written to |
| .bytes              |       |      |          |          | device since boot|
+---------------------+-------+------+----------+----------+------------------+
| hardware.disk.read.\| Gauge | requ\| disk ID  | Pollster | Read requests to |
| requests            |       | ests |          |          | device since boot|
+---------------------+-------+------+----------+----------+------------------+
| hardware.disk.write\| Gauge | requ\| disk ID  | Pollster | Write requests to|
| .requests           |       | ests |          |          | device since boot|
+---------------------+-------+------+----------+----------+------------------+

OpenStack Image service
~~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for OpenStack Image service:

+--------------------+--------+------+----------+----------+------------------+
| Name               | Type   | Unit | Resource | Origin   | Note             |
+====================+========+======+==========+==========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+--------------------+--------+------+----------+----------+------------------+
| image.size         | Gauge  | B    | image ID | Notifica\| Size of the upl\ |
|                    |        |      |          | tion, Po\| oaded image      |
|                    |        |      |          | llster   |                  |
+--------------------+--------+------+----------+----------+------------------+
| image.download     | Delta  | B    | image ID | Notifica\| Image is downlo\ |
|                    |        |      |          | tion     | aded             |
+--------------------+--------+------+----------+----------+------------------+
| image.serve        | Delta  | B    | image ID | Notifica\| Image is served  |
|                    |        |      |          | tion     | out              |
+--------------------+--------+------+----------+----------+------------------+

OpenStack Block Storage
~~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for OpenStack Block Storage:

+--------------------+-------+--------+----------+----------+-----------------+
| Name               | Type  | Unit   | Resource | Origin   | Note            |
+====================+=======+========+==========+==========+=================+
| **Meters added in the Mitaka release or earlier**                           |
+--------------------+-------+--------+----------+----------+-----------------+
| volume.size        | Gauge | GB     | volume ID| Notifica\| Size of the vol\|
|                    |       |        |          | tion     | ume             |
+--------------------+-------+--------+----------+----------+-----------------+
| snapshot.size      | Gauge | GB     | snapshot | Notifica\| Size of the sna\|
|                    |       |        | ID       | tion     | pshot           |
+--------------------+-------+--------+----------+----------+-----------------+
| **Meters added in the Queens release**                                      |
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.ca\| Gauge | GB     | hostname | Notifica\| Total volume    |
| pacity.total       |       |        |          | tion     | capacity on host|
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.ca\| Gauge | GB     | hostname | Notifica\| Free volume     |
| pacity.free        |       |        |          | tion     | capacity on host|
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.ca\| Gauge | GB     | hostname | Notifica\| Assigned volume |
| pacity.allocated   |       |        |          | tion     | capacity on host|
|                    |       |        |          |          | by Cinder       |
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.ca\| Gauge | GB     | hostname | Notifica\| Assigned volume |
| pacity.provisioned |       |        |          | tion     | capacity on host|
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.ca\| Gauge | GB     | hostname | Notifica\| Virtual free    |
| pacity.virtual_free|       |        |          | tion     | volume capacity |
|                    |       |        |          |          | on host         |
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.po\| Gauge | GB     | hostname\| Notifica\| Total volume    |
| ol.capacity.total  |       |        | #pool    | tion     | capacity in pool|
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.po\| Gauge | GB     | hostname\| Notifica\| Free volume     |
| ol.capacity.free   |       |        | #pool    | tion     | capacity in pool|
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.po\| Gauge | GB     | hostname\| Notifica\| Assigned volume |
| ol.capacity.alloca\|       |        | #pool    | tion     | capacity in pool|
| ted                |       |        |          |          | by Cinder       |
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.po\| Gauge | GB     | hostname\| Notifica\| Assigned volume |
| ol.capacity.provis\|       |        | #pool    | tion     | capacity in pool|
| ioned              |       |        |          |          |                 |
+--------------------+-------+--------+----------+----------+-----------------+
| volume.provider.po\| Gauge | GB     | hostname\| Notifica\| Virtual free    |
| ol.capacity.virtua\|       |        | #pool    | tion     | volume capacity |
| l_free             |       |        |          |          | in pool         |
+--------------------+-------+--------+----------+----------+-----------------+

OpenStack File Share
~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for OpenStack File Share:

+--------------------+-------+--------+----------+----------+-----------------+
| Name               | Type  | Unit   | Resource | Origin   | Note            |
+====================+=======+========+==========+==========+=================+
| **Meters added in the Pike release**                                        |
+--------------------+-------+--------+----------+----------+-----------------+
| manila.share.size  | Gauge | GB     | share ID | Notifica\| Size of the fil\|
|                    |       |        |          | tion     | e share         |
+--------------------+-------+--------+----------+----------+-----------------+

.. _telemetry-object-storage-meter:

OpenStack Object Storage
~~~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for OpenStack Object Storage:

+--------------------+-------+-------+------------+---------+-----------------+
| Name               | Type  | Unit  | Resource   | Origin  | Note            |
+====================+=======+=======+============+=========+=================+
| **Meters added in the Mitaka release or earlier**                           |
+--------------------+-------+-------+------------+---------+-----------------+
| storage.objects    | Gauge | object| storage ID | Pollster| Number of objec\|
|                    |       |       |            |         | ts              |
+--------------------+-------+-------+------------+---------+-----------------+
| storage.objects.si\| Gauge | B     | storage ID | Pollster| Total size of s\|
| ze                 |       |       |            |         | tored objects   |
+--------------------+-------+-------+------------+---------+-----------------+
| storage.objects.co\| Gauge | conta\| storage ID | Pollster| Number of conta\|
| ntainers           |       | iner  |            |         | iners           |
+--------------------+-------+-------+------------+---------+-----------------+
| storage.objects.in\| Delta | B     | storage ID | Notific\| Number of incom\|
| coming.bytes       |       |       |            | ation   | ing bytes       |
+--------------------+-------+-------+------------+---------+-----------------+
| storage.objects.ou\| Delta | B     | storage ID | Notific\| Number of outgo\|
| tgoing.bytes       |       |       |            | ation   | ing bytes       |
+--------------------+-------+-------+------------+---------+-----------------+
| storage.containers\| Gauge | object| storage ID\| Pollster| Number of objec\|
| .objects           |       |       | /container |         | ts in container |
+--------------------+-------+-------+------------+---------+-----------------+
| storage.containers\| Gauge | B     | storage ID\| Pollster| Total size of s\|
| .objects.size      |       |       | /container |         | tored objects i\|
|                    |       |       |            |         | n container     |
+--------------------+-------+-------+------------+---------+-----------------+


Ceph Object Storage
~~~~~~~~~~~~~~~~~~~
In order to gather meters from Ceph, you have to install and configure
the Ceph Object Gateway (radosgw) as it is described in the `Installation
Manual <http://docs.ceph.com/docs/master/radosgw/>`__. You also have to enable
`usage logging <http://docs.ceph.com/docs/master/man/8/radosgw/#usage-logging>`__ in
order to get the related meters from Ceph. You will need an
``admin`` user with ``users``, ``buckets``, ``metadata`` and ``usage``
``caps`` configured.

In order to access Ceph from Telemetry, you need to specify a
``service group`` for ``radosgw`` in the ``ceilometer.conf``
configuration file along with ``access_key`` and ``secret_key`` of the
``admin`` user mentioned above.

The following meters are collected for Ceph Object Storage:

+------------------+------+--------+------------+----------+------------------+
| Name             | Type | Unit   | Resource   | Origin   | Note             |
+==================+======+========+============+==========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+------------------+------+--------+------------+----------+------------------+
| radosgw.objects  | Gauge| object | storage ID | Pollster | Number of objects|
+------------------+------+--------+------------+----------+------------------+
| radosgw.objects.\| Gauge| B      | storage ID | Pollster | Total size of s\ |
| size             |      |        |            |          | tored objects    |
+------------------+------+--------+------------+----------+------------------+
| radosgw.objects.\| Gauge| contai\| storage ID | Pollster | Number of conta\ |
| containers       |      | ner    |            |          | iners            |
+------------------+------+--------+------------+----------+------------------+
| radosgw.api.requ\| Gauge| request| storage ID | Pollster | Number of API r\ |
| est              |      |        |            |          | equests against  |
|                  |      |        |            |          | Ceph Object Ga\  |
|                  |      |        |            |          | teway (radosgw)  |
+------------------+------+--------+------------+----------+------------------+
| radosgw.containe\| Gauge| object | storage ID\| Pollster | Number of objec\ |
| rs.objects       |      |        | /container |          | ts in container  |
+------------------+------+--------+------------+----------+------------------+
| radosgw.containe\| Gauge| B      | storage ID\| Pollster | Total size of s\ |
| rs.objects.size  |      |        | /container |          | tored objects in |
|                  |      |        |            |          | container        |
+------------------+------+--------+------------+----------+------------------+

.. note::

    The ``usage`` related information may not be updated right after an
    upload or download, because the Ceph Object Gateway needs time to
    update the usage properties. For instance, the default configuration
    needs approximately 30 minutes to generate the usage logs.

OpenStack Identity
~~~~~~~~~~~~~~~~~~

The following meters are collected for OpenStack Identity:

+-------------------+------+--------+-----------+-----------+-----------------+
| Name              | Type | Unit   | Resource  | Origin    | Note            |
+===================+======+========+===========+===========+=================+
| **Meters added in the Mitaka release or earlier**                           |
+-------------------+------+--------+-----------+-----------+-----------------+
| identity.authent\ | Delta| user   | user ID   | Notifica\ | User successful\|
| icate.success     |      |        |           | tion      | ly authenticated|
+-------------------+------+--------+-----------+-----------+-----------------+
| identity.authent\ | Delta| user   | user ID   | Notifica\ | User pending au\|
| icate.pending     |      |        |           | tion      | thentication    |
+-------------------+------+--------+-----------+-----------+-----------------+
| identity.authent\ | Delta| user   | user ID   | Notifica\ | User failed to  |
| icate.failure     |      |        |           | tion      | authenticate    |
+-------------------+------+--------+-----------+-----------+-----------------+

OpenStack Networking
~~~~~~~~~~~~~~~~~~~~

The following meters are collected for OpenStack Networking:

+-----------------+-------+--------+-----------+-----------+------------------+
| Name            | Type  | Unit   | Resource  | Origin    | Note             |
+=================+=======+========+===========+===========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+-----------------+-------+--------+-----------+-----------+------------------+
| bandwidth       | Delta | B      | label ID  | Notifica\ | Bytes through t\ |
|                 |       |        |           | tion      | his l3 metering  |
|                 |       |        |           |           | label            |
+-----------------+-------+--------+-----------+-----------+------------------+

SDN controllers
~~~~~~~~~~~~~~~

The following meters are collected for SDN:

+-----------------+---------+--------+-----------+----------+-----------------+
| Name            | Type    | Unit   | Resource  | Origin   | Note            |
+=================+=========+========+===========+==========+=================+
| **Meters added in the Mitaka release or earlier**                           |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch          | Gauge   | switch | switch ID | Pollster | Existence of sw\|
|                 |         |        |           |          | itch            |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port     | Gauge   | port   | switch ID | Pollster | Existence of po\|
|                 |         |        |           |          | rt              |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.re\ | Cumula\ | packet | switch ID | Pollster | Packets receive\|
| ceive.packets   | tive    |        |           |          | d on port       |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.tr\ | Cumula\ | packet | switch ID | Pollster | Packets transmi\|
| ansmit.packets  | tive    |        |           |          | tted on port    |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.re\ | Cumula\ | B      | switch ID | Pollster | Bytes received  |
| ceive.bytes     | tive    |        |           |          | on port         |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.tr\ | Cumula\ | B      | switch ID | Pollster | Bytes transmitt\|
| ansmit.bytes    | tive    |        |           |          | ed on port      |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.re\ | Cumula\ | packet | switch ID | Pollster | Drops received  |
| ceive.drops     | tive    |        |           |          | on port         |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.tr\ | Cumula\ | packet | switch ID | Pollster | Drops transmitt\|
| ansmit.drops    | tive    |        |           |          | ed on port      |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.re\ | Cumula\ | packet | switch ID | Pollster | Errors received |
| ceive.errors    | tive    |        |           |          | on port         |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.tr\ | Cumula\ | packet | switch ID | Pollster | Errors transmit\|
| ansmit.errors   | tive    |        |           |          | ted on port     |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.re\ | Cumula\ | packet | switch ID | Pollster | Frame alignment |
| ceive.frame\_er\| tive    |        |           |          | errors receive\ |
| ror             |         |        |           |          | d on port       |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.re\ | Cumula\ | packet | switch ID | Pollster | Overrun errors  |
| ceive.overrun\_\| tive    |        |           |          | received on port|
| error           |         |        |           |          |                 |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.re\ | Cumula\ | packet | switch ID | Pollster | CRC errors rece\|
| ceive.crc\_error| tive    |        |           |          | ived on port    |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.co\ | Cumula\ | count  | switch ID | Pollster | Collisions on p\|
| llision.count   | tive    |        |           |          | ort             |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.table    | Gauge   | table  | switch ID | Pollster | Duration of tab\|
|                 |         |        |           |          | le              |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.table.a\ | Gauge   | entry  | switch ID | Pollster | Active entries  |
| ctive.entries   |         |        |           |          | in table        |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.table.l\ | Gauge   | packet | switch ID | Pollster | Lookup packets  |
| ookup.packets   |         |        |           |          | for table       |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.table.m\ | Gauge   | packet | switch ID | Pollster | Packets matches |
| atched.packets  |         |        |           |          | for table       |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.flow     | Gauge   | flow   | switch ID | Pollster | Duration of flow|
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.flow.du\ | Gauge   | s      | switch ID | Pollster | Duration of flow|
| ration.seconds  |         |        |           |          | in seconds      |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.flow.du\ | Gauge   | ns     | switch ID | Pollster | Duration of flow|
| ration.nanosec\ |         |        |           |          | in nanoseconds  |
| onds            |         |        |           |          |                 |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.flow.pa\ | Cumula\ | packet | switch ID | Pollster | Packets received|
| ckets           | tive    |        |           |          |                 |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.flow.by\ | Cumula\ | B      | switch ID | Pollster | Bytes received  |
| tes             | tive    |        |           |          |                 |
+-----------------+---------+--------+-----------+----------+-----------------+
| **Meters added in the Pike release**                                        |
+-----------------+---------+--------+-----------+----------+-----------------+
| port            | Gauge   | port   | port ID   | Pollster | Existence of po\|
|                 |         |        |           |          | rt              |
+-----------------+---------+--------+-----------+----------+-----------------+
| port.uptime     | Gauge   | s      | port ID   | Pollster | Uptime of port  |
|                 |         |        |           |          |                 |
+-----------------+---------+--------+-----------+----------+-----------------+
| port.receive.pa\| Cumula\ | packet | port ID   | Pollster | Packets trasmit\|
| ckets           | tive    |        |           |          | ted on port     |
+-----------------+---------+--------+-----------+----------+-----------------+
| port.transmit.\ | Cumula\ | packet | port ID   | Pollster | Packets transmi\|
| packets         | tive    |        |           |          | tted on port    |
+-----------------+---------+--------+-----------+----------+-----------------+
| port.receive.\  | Cumula\ | B      | port ID   | Pollster | Bytes received  |
| bytes           | tive    |        |           |          | on port         |
+-----------------+---------+--------+-----------+----------+-----------------+
| port.transmit.\ | Cumula\ | B      | port ID   | Pollster | Bytes transmitt\|
| bytes           | tive    |        |           |          | ed on port      |
+-----------------+---------+--------+-----------+----------+-----------------+
| port.receive.\  | Cumula\ | packet | port ID   | Pollster | Drops received  |
| drops           | tive    |        |           |          | on port         |
+-----------------+---------+--------+-----------+----------+-----------------+
| port.receive.\  | Cumula\ | packet | port ID   | Pollster | Errors received |
| errors          | tive    |        |           |          | on port         |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.ports    | Gauge   | ports  | switch ID | Pollster | Number of ports\|
|                 |         |        |           |          | on switch       |
+-----------------+---------+--------+-----------+----------+-----------------+
| switch.port.upt\| Gauge   | s      | switch ID | Pollster | Uptime of switch|
| ime             |         |        |           |          |                 |
+-----------------+---------+--------+-----------+----------+-----------------+

These meters are available for OpenFlow based switches. In order to
enable these meters, each driver needs to be properly configured.

Load-Balancer-as-a-Service (LBaaS v1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for LBaaS v1:

+---------------+---------+---------+-----------+-----------+-----------------+
| Name          | Type    | Unit    | Resource  | Origin    | Note            |
+===============+=========+=========+===========+===========+=================+
| **Meters added in the Mitaka release or earlier**                           |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | pool    | pool ID   | Pollster  | Existence of a  |
| ices.lb.pool  |         |         |           |           | LB pool         |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | vip     | vip ID    | Pollster  | Existence of a  |
| ices.lb.vip   |         |         |           |           | LB VIP          |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | member  | member ID | Pollster  | Existence of a  |
| ices.lb.memb\ |         |         |           |           | LB member       |
| er            |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | health\ | monitor ID| Pollster  | Existence of a  |
| ices.lb.heal\ |         | _monit\ |           |           | LB health probe |
| th_monitor    |         | or      |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Cumula\ | connec\ | pool ID   | Pollster  | Total connectio\|
| ices.lb.tota\ | tive    | tion    |           |           | ns on a LB      |
| l.connections |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | connec\ | pool ID   | Pollster  | Active connecti\|
| ices.lb.acti\ |         | tion    |           |           | ons on a LB     |
| ve.connections|         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | B       | pool ID   | Pollster  | Number of incom\|
| ices.lb.inco\ |         |         |           |           | ing Bytes       |
| ming.bytes    |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | B       | pool ID   | Pollster  | Number of outgo\|
| ices.lb.outg\ |         |         |           |           | ing Bytes       |
| oing.bytes    |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+

Load-Balancer-as-a-Service (LBaaS v2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for LBaaS v2.

+---------------+---------+---------+-----------+-----------+-----------------+
| Name          | Type    | Unit    | Resource  | Origin    | Note            |
+===============+=========+=========+===========+===========+=================+
| **Meters added in the Mitaka release or earlier**                           |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | pool    | pool ID   | Pollster  | Existence of a  |
| ices.lb.pool  |         |         |           |           | LB pool         |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | listen\ | listener  | Pollster  | Existence of a  |
| ices.lb.list\ |         | er      | ID        |           | LB listener     |
| ener          |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | member  | member ID | Pollster  | Existence of a  |
| ices.lb.memb\ |         |         |           |           | LB member       |
| er            |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | health\ | monitor ID| Pollster  | Existence of a  |
| ices.lb.heal\ |         | _monit\ |           |           | LB health probe |
| th_monitor    |         | or      |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | loadba\ | loadbala\ | Pollster  | Existence of a  |
| ices.lb.load\ |         | lancer  | ncer ID   |           | LB loadbalancer |
| balancer      |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Cumula\ | connec\ | pool ID   | Pollster  | Total connectio\|
| ices.lb.tota\ | tive    | tion    |           |           | ns on a LB      |
| l.connections |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | connec\ | pool ID   | Pollster  | Active connecti\|
| ices.lb.acti\ |         | tion    |           |           | ons on a LB     |
| ve.connections|         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | B       | pool ID   | Pollster  | Number of incom\|
| ices.lb.inco\ |         |         |           |           | ing Bytes       |
| ming.bytes    |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+
| network.serv\ | Gauge   | B       | pool ID   | Pollster  | Number of outgo\|
| ices.lb.outg\ |         |         |           |           | ing Bytes       |
| oing.bytes    |         |         |           |           |                 |
+---------------+---------+---------+-----------+-----------+-----------------+

.. note::

   The above meters are experimental and may generate a large load against the
   Neutron APIs. The future enhancement will be implemented when Neutron
   supports the new APIs.

VPN-as-a-Service (VPNaaS)
~~~~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for VPNaaS:

+---------------+-------+---------+------------+-----------+------------------+
| Name          | Type  | Unit    | Resource   | Origin    | Note             |
+===============+=======+=========+============+===========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+---------------+-------+---------+------------+-----------+------------------+
| network.serv\ | Gauge | vpnser\ | vpn ID     | Pollster  | Existence of a   |
| ices.vpn      |       | vice    |            |           | VPN              |
+---------------+-------+---------+------------+-----------+------------------+
| network.serv\ | Gauge | ipsec\_\| connection | Pollster  | Existence of an  |
| ices.vpn.con\ |       | site\_c\| ID         |           | IPSec connection |
| nections      |       | onnect\ |            |           |                  |
|               |       | ion     |            |           |                  |
+---------------+-------+---------+------------+-----------+------------------+

Firewall-as-a-Service (FWaaS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following meters are collected for FWaaS:

+---------------+-------+---------+------------+-----------+------------------+
| Name          | Type  | Unit    | Resource   | Origin    | Note             |
+===============+=======+=========+============+===========+==================+
| **Meters added in the Mitaka release or earlier**                           |
+---------------+-------+---------+------------+-----------+------------------+
| network.serv\ | Gauge | firewall| firewall ID| Pollster  | Existence of a   |
| ices.firewall |       |         |            |           | firewall         |
+---------------+-------+---------+------------+-----------+------------------+
| network.serv\ | Gauge | firewa\ | firewall ID| Pollster  | Existence of a   |
| ices.firewal\ |       | ll_pol\ |            |           | firewall policy  |
| l.policy      |       | icy     |            |           |                  |
+---------------+-------+---------+------------+-----------+------------------+
