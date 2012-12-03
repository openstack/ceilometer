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


Here are the meter types by components that are currently implemented:

Compute (Nova)
==============

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
instance                  Gauge             1  inst ID   Duration of instance
instance:<type>           Gauge             1  inst ID   Duration of instance <type> (openstack types)
memory                    Gauge            MB  inst ID   Volume of RAM in MB
cpu                       Cumulative       ns  inst ID   CPU time used
vcpus                     Gauge          vcpu  inst ID   Number of VCPUs
disk.root.size            Gauge            GB  inst ID   Size of root disk in GB
disk.ephemeral.size       Gauge            GB  inst ID   Size of ephemeral disk in GB
disk.io.requests          Cumulative  request  inst ID   Number of disk io requests
disk.io.bytes             Cumulative    bytes  inst ID   Volume of disk io in bytes
network.incoming.bytes    Cumulative    bytes  iface ID  number of incoming bytes on the network
network.outgoing.bytes    Cumulative    bytes  iface ID  number of outgoing bytes on the network
network.incoming.packets  Cumulative  packets  iface ID  number of incoming packets
network.outgoing.packets  Cumulative  packets  iface ID  number of outgoing packets
========================  ==========  =======  ========  =======================================================

Network (Quantum)
=================

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
network                   Gauge             1  netw ID   Duration of network
network.create            Delta       request  netw ID   Creation requests for this network
network.update            Delta       request  netw ID   Update requests for this network
subnet                    Gauge             1  subnt ID  Duration of subnet
subnet.create             Delta       request  subnt ID  Creation requests for this subnet
subnet.update             Delta       request  subnt ID  Update requests for this subnet
port                      Gauge             1  port ID   Duration of port
port.create               Delta       request  port ID   Creation requests for this port
port.update               Delta       request  port ID   Update requests for this port
router                    Gauge             1  rtr ID    Duration of router
router.create             Delta       request  rtr ID    Creation requests for this router
router.update             Delta       request  rtr ID    Update requests for this router
ip.floating               Gauge             1  ip ID     Duration of floating ip
ip.floating.create        Delta             1  ip ID     Creation requests for this floating ip
ip.floating.update        Delta             1  ip ID     Update requests for this floating ip
========================  ==========  =======  ========  =======================================================

Image (Glance)
==============

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
image                     Gauge             1  image ID  Image polling -> it (still) exists
image.size                Gauge         bytes  image ID  Uploaded image size
image.update              Delta          reqs  image ID  Number of update on the image
image.upload              Delta          reqs  image ID  Number of upload of the image
image.delete              Delta          reqs  image ID  Number of delete on the image
image.download            Delta         bytes  image ID  Image is downloaded
image.serve               Delta         bytes  image ID  Image is served out
========================  ==========  =======  ========  =======================================================

Volume (Cinder)
===============

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
volume                    Gauge             1  vol ID    Duration of volune
volume.size               Gauge            GB  vol ID    Size of volume
========================  ==========  =======  ========  =======================================================

Object Storage (Swift)
======================

==========================  ==========  ==========  ========  ==================================================
Name                        Type        Volume      Resource  Note
==========================  ==========  ==========  ========  ==================================================
storage.objects             Gauge          objects  store ID  Number of objects
storage.objects.size        Gauge            bytes  store ID  Total size of stored objects
storage.objects.containers  Gauge       containers  store ID  Number of containers
==========================  ==========  ==========  ========  ==================================================

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
