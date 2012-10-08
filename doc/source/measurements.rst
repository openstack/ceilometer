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

Here are the counter types by components that are currently implemented:

Compute (Nova)
==============

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
instance                  Gauge             1  inst ID   Duration of instance
memory                    Gauge            MB  inst ID   Volume of RAM in MB
vcpus                     Gauge          vcpu  inst ID   Number of VCPUs
root_disk_size            Gauge            GB  inst ID   Size of root disk in GB
ephemeral_disk_size       Gauge            GB  inst ID   Size of ephemeral disk in GB
instance:type             Gauge             1  inst ID   Duration of instance type
disk.io.requests          Cumulative  request  inst ID   Number of disk io requests
disk.io.bytes             Cumulative    bytes  inst ID   Volume of disk io in bytes
cpu                       Cumulative  seconds  inst ID   CPU time used
network.incoming.bytes    Cumulative    bytes  inst ID   number of incoming bytes on the network
network.outgoing.bytes    Cumulative    bytes  inst ID   number of outgoing bytes on the network
network.incoming.packets  Cumulative  packets  inst ID   number of incoming packets
network.outgoing.packets  Cumulative  packets  inst ID   number of outgoing packets
========================  ==========  =======  ========  =======================================================

Network (Quantum)
=================

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
network                   Gauge             1  netw ID   Duration of network
network.create            Gauge             1  network
network.update            Gauge             1  network
network.exists            Gauge             1  network
subnet                    Gauge             1  subnt ID  Duration of subnet
subnet.create             Gauge             1  network
subnet.update             Gauge             1  network
subnet.exists             Gauge             1  network
port                      Gauge             1  port ID   Duration of port
port.create               Gauge             1  network
port.update               Gauge             1  network
port.exists               Gauge             1  network
floating_ip               Gauge             1  ip ID     Duration of floating ip
========================  ==========  =======  ========  =======================================================

Image (Glance)
==============

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
image                     Gauge             1  image ID  Image polling -> it (still) exists
image_size                Gauge         bytes  image ID  Uploaded image size
image_download            Gauge         bytes  image ID  Image is downloaded
image_serve               Gauge         bytes  image ID  Image is served out
========================  ==========  =======  ========  =======================================================

Volume (Cinder)
===============

========================  ==========  =======  ========  =======================================================
Name                      Type        Volume   Resource  Note
========================  ==========  =======  ========  =======================================================
volume                    Gauge             1  vol ID    Duration of volune
volume_size               Gauge            GB  vol ID    Size of volume
========================  ==========  =======  ========  =======================================================


