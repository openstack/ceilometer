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

Units should use common abbreviatons:

============  ========  ==============  =====
Dimension     Unit      Abbreviations      Note
============  ========  ==============  =====
None          N/A                       Dimension-less variable
Volume        byte                   B
Time          seconds                s

Information units should be expressed in bits ('b') or bytes ('B').

Here are the meter types by components that are currently implemented:

Compute (Nova)
==============

========================  ==========  ========  ========  =======================================================
Name                      Type        Unit     Resource  Note
========================  ==========  ========  ========  =======================================================
instance                  Gauge                 inst ID   Duration of instance
instance:<type>           Gauge                 inst ID   Duration of instance <type> (openstack types)
memory                    Gauge              B  inst ID   Volume of RAM in MB
cpu                       Cumulative        ns  inst ID   CPU time used
vcpus                     Gauge           vcpu  inst ID   Number of VCPUs
disk.root.size            Gauge              B  inst ID   Size of root disk in GB
disk.ephemeral.size       Gauge              B  inst ID   Size of ephemeral disk in GB
disk.io.requests          Cumulative  requests  inst ID   Number of disk io requests
disk.io.bytes             Cumulative         B  inst ID   Volume of disk io in bytes
network.incoming.bytes    Cumulative         B  iface ID  number of incoming bytes on the network
network.outgoing.bytes    Cumulative         B  iface ID  number of outgoing bytes on the network
network.incoming.packets  Cumulative   packets  iface ID  number of incoming packets
network.outgoing.packets  Cumulative   packets  iface ID  number of outgoing packets
========================  ==========  ========  ========  =======================================================

Network (Quantum)
=================

========================  ==========  ========  ========  ======================================================
Name                      Type        Unit      Resource  Note
========================  ==========  ========  ========  ======================================================
network                   Gauge       network   netw ID   Duration of network
network.create            Delta       network   netw ID   Creation requests for this network
network.update            Delta       network   netw ID   Update requests for this network
subnet                    Gauge       subnet    subnt ID  Duration of subnet
subnet.create             Delta       subnet    subnt ID  Creation requests for this subnet
subnet.update             Delta       subnet    subnt ID  Update requests for this subnet
port                      Gauge       port      port ID   Duration of port
port.create               Delta       port      port ID   Creation requests for this port
port.update               Delta       port      port ID   Update requests for this port
router                    Gauge       router    rtr ID    Duration of router
router.create             Delta       router    rtr ID    Creation requests for this router
router.update             Delta       router    rtr ID    Update requests for this router
ip.floating               Gauge       ip        ip ID     Duration of floating ip
ip.floating.create        Delta       ip        ip ID     Creation requests for this floating ip
ip.floating.update        Delta       ip        ip ID     Update requests for this floating ip
========================  ==========  ========  ========  ======================================================

Image (Glance)
==============

========================  ==========  =======  ========  =======================================================
Name                      Type        Unit     Resource  Note
========================  ==========  =======  ========  =======================================================
image                     Gauge         image  image ID  Image polling -> it (still) exists
image.size                Gauge             B  image ID  Uploaded image size
image.update              Delta         image  image ID  Number of update on the image
image.upload              Delta         image  image ID  Number of upload of the image
image.delete              Delta         image  image ID  Number of delete on the image
image.download            Delta             B  image ID  Image is downloaded
image.serve               Delta             B  image ID  Image is served out
========================  ==========  =======  ========  =======================================================

Volume (Cinder)
===============

========================  ==========  =======  ========  =======================================================
Name                      Type        Unit     Resource  Note
========================  ==========  =======  ========  =======================================================
volume                    Gauge        volume  vol ID    Duration of volune
volume.size               Gauge           GiB  vol ID    Size of volume
========================  ==========  =======  ========  =======================================================

Object Storage (Swift)
======================

==========================      ==========  ==========  ========  ==============================================
Name                            Type        Volume      Resource  Note
==========================      ==========  ==========  ========  ==============================================
storage.objects                 Gauge          objects  store ID  Number of objects
storage.objects.size            Gauge                B  store ID  Total size of stored objects
storage.objects.containers      Gauge       containers  store ID  Number of containers
storage.objects.incoming.bytes  Delta                B  store ID  Number of incoming bytes
storage.objects.outgoing.bytes  Delta                B  store ID  Number of outgoing bytes
==============================  ==========  ==========  ========  ==============================================

Dynamically retrieving the Meters via ceilometer client
=======================================================
    ceilometer meter-list -s openstack
    +------------+-------+--------------------------------------+---------+----------------------------------+
    | Name       | Type  | Resource ID                          | User ID | Project ID                       |
    +------------+-------+--------------------------------------+---------+----------------------------------+
    | image      | gauge | 09e84d97-8712-4dd2-bcce-45970b2430f7 |         | 57cf6d93688e4d39bf2fe3d3c03eb326 |

The above command will retrieve the available meters that can be queried on
given the actual resource instances available.


Naming convention
=================
If you plan on adding meters, please follow the convention bellow:

1. Always use '.' as separator and go from least to most discriminent word.
   For example, do not use ephemeral_disk_size but disk.ephemeral.size

2. When a part of the name is a variable, it should always be at the end and start with a ':'.
   For example do not use <type>.image but image:<type>, where type is your variable name.

3. If you have any hesitation, come and ask in #openstack-metering
