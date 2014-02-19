..
      Copyright 2012 New Dream Network (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _measurements:

==============
 Measurements
==============

Three type of meters are defined in ceilometer:

.. index::
   double: meter; cumulative
   double: meter; gauge
   double: meter; delta

==========  ==============================================================================
Type        Definition
==========  ==============================================================================
Cumulative  Increasing over time (instance hours)
Gauge       Discrete items (floating IPs, image uploads) and fluctuating values (disk I/O)
Delta       Changing over time (bandwidth)
==========  ==============================================================================

Units
=====

1. Whenever a volume is to be measured, SI approved units and their
   approved symbols or abbreviations should be used. Information units
   should be expressed in bits ('b') or bytes ('B').
2. For a given meter, the units should NEVER, EVER be changed.
3. When the measurement does not represent a volume, the unit
   description should always described WHAT is measured (ie: apples,
   disk, routers, floating IPs, etc.).
4. When creating a new meter, if another meter exists measuring
   something similar, the same units and precision should be used.
5. Meters and samples should always document their units in Ceilometer (API
   and Documentation) and new sampling code should not be merged without the
   appropriate documentation.

============  ========  ==============  =====
Dimension     Unit      Abbreviations   Note
============  ========  ==============  =====
None          N/A                       Dimension-less variable
Volume        byte      B
Time          seconds   s
============  ========  ==============  =====

Here are the meter types by components that are currently implemented:

Compute (Nova)
==============

All meters are related to the guest machine, not the host.

=============================  ==========  =========  ========  ============  ==================================================================
Name                           Type        Unit       Resource  Origin        Note
=============================  ==========  =========  ========  ============  ==================================================================
instance                       Gauge       instance   inst ID   both          Existence of instance
instance:<type>                Gauge       instance   inst ID   both          Existence of instance <type> (openstack types)
memory                         Gauge       MB         inst ID   notification  Volume of RAM in MB
cpu                            Cumulative  ns         inst ID   pollster      CPU time used
cpu_util                       Gauge       %          inst ID   pollster      Average CPU utilisation
vcpus                          Gauge       vcpu       inst ID   notification  Number of VCPUs
disk.read.requests             Cumulative  request    inst ID   pollster      Number of read requests
disk.read.requests.rate        Gauge       request/s  inst ID   pollster      Average rate of read requests per second
disk.write.requests            Cumulative  request    inst ID   pollster      Number of write requests
disk.write.requests.rate       Cumulative  request/s  inst ID   pollster      Average rate of write requests per second
disk.read.bytes                Cumulative  B          inst ID   pollster      Volume of reads in B
disk.read.bytes.rate           Cumulative  B/s        inst ID   pollster      Average rate of reads in B per second
disk.write.bytes               Cumulative  B          inst ID   pollster      Volume of writes in B
disk.write.bytes.rate          Cumulative  B/s        inst ID   pollster      Average volume of writes in B per second
disk.root.size                 Gauge       GB         inst ID   notification  Size of root disk in GB
disk.ephemeral.size            Gauge       GB         inst ID   notification  Size of ephemeral disk in GB
network.incoming.bytes         Cumulative  B          iface ID  pollster      Number of incoming bytes on a VM network interface
network.incoming.bytes.rate    Gauge       B/s        iface ID  pollster      Average rate per sec of incoming bytes on a VM network interface
network.outgoing.bytes         Cumulative  B          iface ID  pollster      Number of outgoing bytes on a VM network interface
network.outgoing.bytes.rate    Gauge       B/s        iface ID  pollster      Average rate per sec of outgoing bytes on a VM network interface
network.incoming.packets       Cumulative  packet     iface ID  pollster      Number of incoming packets on a VM network interface
network.incoming.packets.rate  Gauge       packet/s   iface ID  pollster      Average rate per sec of incoming packets on a VM network interface
network.outgoing.packets       Cumulative  packet     iface ID  pollster      Number of outgoing packets on a VM network interface
network.outgoing.packets.rate  Gauge       packet/s   iface ID  pollster      Average rate per sec of outgoing packets on a VM network interface
=============================  ==========  =========  ========  ============  ==================================================================

At present, most of the Nova meters will only work with libvirt front-end
hypervisors while test coverage was mostly done based on KVM. Contributors
are welcome to implement other virtualization backends' meters or complete
the existing ones.

Network (Neutron)
=================

========================  ==========  ========  ========  ============  ======================================================
Name                      Type        Unit      Resource  Origin        Note
========================  ==========  ========  ========  ============  ======================================================
network                   Gauge       network   netw ID   notification  Existence of network
network.create            Delta       network   netw ID   notification  Creation requests for this network
network.update            Delta       network   netw ID   notification  Update requests for this network
subnet                    Gauge       subnet    subnt ID  notification  Existence of subnet
subnet.create             Delta       subnet    subnt ID  notification  Creation requests for this subnet
subnet.update             Delta       subnet    subnt ID  notification  Update requests for this subnet
port                      Gauge       port      port ID   notification  Existence of port
port.create               Delta       port      port ID   notification  Creation requests for this port
port.update               Delta       port      port ID   notification  Update requests for this port
router                    Gauge       router    rtr ID    notification  Existence of router
router.create             Delta       router    rtr ID    notification  Creation requests for this router
router.update             Delta       router    rtr ID    notification  Update requests for this router
ip.floating               Gauge       ip        ip ID     both          Existence of floating ip
ip.floating.create        Delta       ip        ip ID     notification  Creation requests for this floating ip
ip.floating.update        Delta       ip        ip ID     notification  Update requests for this floating ip
========================  ==========  ========  ========  ============  ======================================================

Image (Glance)
==============

========================  ==========  =======  ========  ============  =======================================================
Name                      Type        Unit     Resource  Origin        Note
========================  ==========  =======  ========  ============  =======================================================
image                     Gauge       image    image ID  both          Image polling -> it (still) exists
image.size                Gauge       B        image ID  both          Uploaded image size
image.update              Delta       image    image ID  notification  Number of update on the image
image.upload              Delta       image    image ID  notification  Number of upload of the image
image.delete              Delta       image    image ID  notification  Number of delete on the image
image.download            Delta       B        image ID  notification  Image is downloaded
image.serve               Delta       B        image ID  notification  Image is served out
========================  ==========  =======  ========  ============  =======================================================

Volume (Cinder)
===============

========================  ==========  =======  ========  ============  =======================================================
Name                      Type        Unit     Resource  Origin        Note
========================  ==========  =======  ========  ============  =======================================================
volume                    Gauge       volume   vol ID    notification  Existence of volume
volume.size               Gauge       GB       vol ID    notification  Size of volume
========================  ==========  =======  ========  ============  =======================================================

Make sure Cinder is properly configured first: see :ref:`installing_manually`.

Object Storage (Swift)
======================

===============================  ==========  ==========  ===========  ============  ==========================================
Name                             Type        Unit        Resource     Origin        Note
===============================  ==========  ==========  ===========  ============  ==========================================
storage.objects                  Gauge       object      store ID     pollster      Number of objects
storage.objects.size             Gauge       B           store ID     pollster      Total size of stored objects
storage.objects.containers       Gauge       container   store ID     pollster      Number of containers
storage.objects.incoming.bytes   Delta       B           store ID     notification  Number of incoming bytes
storage.objects.outgoing.bytes   Delta       B           store ID     notification  Number of outgoing bytes
storage.api.request              Delta       request     store ID     notification  Number of API requests against swift
storage.containers.objects       Gauge       object      str ID/cont  pollster      Number of objects in container
storage.containers.objects.size  Gauge       B           str ID/cont  pollster      Total size of stored objects in container
===============================  ==========  ==========  ===========  ============  ==========================================

In order to use storage.objects.incoming.bytes and storage.outgoing.bytes, one must configure
Swift as described in :ref:`installing_manually`. Note that they may not be
updated right after an upload/download, since Swift takes some time to update
the container properties.

Orchestration (Heat)
====================

===============================  ==========  ==========  ===========  ============  ==========================================
Name                             Type        Unit        Resource     Origin        Note
===============================  ==========  ==========  ===========  ============  ==========================================
stack.create                     Delta       stack       stack ID     notification  Creation requests for a stack successful
stack.update                     Delta       stack       stack ID     notification  Updating requests for a stack successful
stack.delete                     Delta       stack       stack ID     notification  Deletion requests for a stack successful
stack.resume                     Delta       stack       stack ID     notification  Resuming requests for a stack successful
stack.suspend                    Delta       stack       stack ID     notification  Suspending requests for a stack successful
===============================  ==========  ==========  ===========  ============  ==========================================

To enable Heat notifications configure Heat as described in :ref:`installing_manually`.

Energy (Kwapi)
==============

==========================  ==========  ==========  ========  ========= ==============================================
Name                        Type        Unit        Resource  Origin    Note
==========================  ==========  ==========  ========  ========= ==============================================
energy                      Cumulative  kWh         probe ID  pollster  Amount of energy
power                       Gauge       W           probe ID  pollster  Power consumption
==========================  ==========  ==========  ========  ========= ==============================================

Dynamically retrieving the Meters via ceilometer client
=======================================================

To retrieve the available meters that can be queried given the actual
resource instances available, use the ``meter-list`` command:

::

    $ ceilometer meter-list -s openstack
    +------------+-------+--------------------------------------+---------+----------------------------------+
    | Name       | Type  | Resource ID                          | User ID | Project ID                       |
    +------------+-------+--------------------------------------+---------+----------------------------------+
    | image      | gauge | 09e84d97-8712-4dd2-bcce-45970b2430f7 |         | 57cf6d93688e4d39bf2fe3d3c03eb326 |


Naming convention
=================
If you plan on adding meters, please follow the convention bellow:

1. Always use '.' as separator and go from least to most discriminant word.
   For example, do not use ephemeral_disk_size but disk.ephemeral.size

2. When a part of the name is a variable, it should always be at the end and start with a ':'.
   For example do not use <type>.image but image:<type>, where type is your variable name.

3. If you have any hesitation, come and ask in #openstack-ceilometer


User-defined sample metadata for Nova
=========================================

Users are allowed to add additional metadata to samples of nova meter.
These additional metadata are stored in 'resource_metadata.user_metadata.*' of the sample
To do so, users should add nova user metadata prefixed with 'metering.':

::
    $ nova boot --meta metering.custom_metadata=a_value my_vm

Note: The name of the metadata shouldn't exceed 256 characters otherwise it will be cut off.
Also, if it has '.', this will be replaced by a '_' in ceilometer.

User-defined sample metadata for Swift
==========================================
It's possible to add additional metadata to sample of Swift meter as well.
You might specify headers whose values will be stored in resource_metadata as
'resource_metadata.http_header_$name', where $name is a name of the header with
'-' replaced by '_'.

This is done using 'metadata_headers' option in middleware configuration,
refer to :ref:`installing_manually` for details.

For example, this could be used to distinguish external and internal users. You'd
have to implement a custom Swift middleware that sets a proper header and just add
it to metadata_headers.
