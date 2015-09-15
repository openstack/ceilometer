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

.. _add_new_meters:

==================
 New measurements
==================

Ceilometer is designed to collect measurements from OpenStack services and
from other external components. If you would like to add new meters to the
currently existing ones, you need to follow the guidelines given in this
section.

.. _meter_types:

Types
=====

Three type of meters are defined in Ceilometer:

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

When you're about to add a new meter choose one type from the above list, which
is applicable.


Units
=====

1. Whenever a volume is to be measured, SI approved units and their
   approved symbols or abbreviations should be used. Information units
   should be expressed in bits ('b') or bytes ('B').
2. For a given meter, the units should NEVER, EVER be changed.
3. When the measurement does not represent a volume, the unit
   description should always describe WHAT is measured (ie: apples,
   disk, routers, floating IPs, etc.).
4. When creating a new meter, if another meter exists measuring
   something similar, the same units and precision should be used.
5. Meters and samples should always document their units in Ceilometer (API
   and Documentation) and new sampling code should not be merged without the
   appropriate documentation.

============  ========  ==============  =======================
Dimension     Unit      Abbreviations   Note
============  ========  ==============  =======================
None          N/A                       Dimension-less variable
Volume        byte      B
Time          seconds   s
============  ========  ==============  =======================


Meters
======

Naming convention
-----------------

If you plan on adding meters, please follow the convention below:

1. Always use '.' as separator and go from least to most discriminant word.
   For example, do not use ephemeral_disk_size but disk.ephemeral.size

2. When a part of the name is a variable, it should always be at the end and start with a ':'.
   For example do not use <type>.image but image:<type>, where type is your variable name.

3. If you have any hesitation, come and ask in #openstack-ceilometer

Meter definitions
-----------------
Meters definitions by default, are stored in separate configuration
file, called :file:`ceilometer/meter/data/meter.yaml`. This is essentially
a replacement for prior approach of writing notification handlers to consume
specific topics.

A detailed description of how to use meter definition is illustrated in
the `admin_guide`_.

.. _admin_guide: http://docs.openstack.org/admin-guide-cloud/telemetry-data-collection.html#meter-definitions

Non-metric meters and events
----------------------------

Ceilometer supports collecting notifications as events. It is highly
recommended to use events for capturing if something happened in the system
or not as opposed to defining meters of which volume will be constantly '1'.
Events enable better representation and querying of metadata rather than
statistical aggregations required for Samples. When the event support is
turned on for Ceilometer, event type meters are collected into the event
database too, which can lead to the duplication of a huge amount of data.

In order to learn more about events see the :ref:`events` section.
