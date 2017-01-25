..
      Copyright 2013 Nicolas Barcet for eNovance

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _choosing_db_backend:

============================
 Choosing a database backend
============================

Moving from Ceilometer to Gnocchi
=================================

Gnocchi represents a fundamental change in how data is represented and stored.
Installation and configuration can be found in :ref:`installing_manually`.
Differences between APIs can be found here_.

There currently exists no migration tool between the services. To transition
to Gnocchi, multiple dispatchers can be enabled in the Collector to capture
data in both the native Ceilometer database and Gnocchi. This will allow you
to test Gnocchi and transition to it fully when comfortable. The following
should be included in addition to the required configurations for each
backend::

  [DEFAULT]
  meter_dispatchers=database
  meter_dispatchers=gnocchi
  event_dispatchers=gnocchi

Disable Keystone Authentification for Gnocchi
=============================================

In somes cases, it is possible to disable keystone authentication for
Gnocchi to remove the overhead of token creation/verification when request
authentication doesn't matter. This will increase the performance of Gnocchi.

Example of configuration::

    [dispatcher_gnocchi]
    auth_section=service_credentials_gnocchi

    [service_credentials_gnocchi]
    auth_type=gnocchi-noauth
    roles = admin
    user_id = <ceilometer_user_id>
    project_id = <ceilometer_project_id>
    endpoint = <gnocchi_endpoint>

.. _Gnocchi: http://gnocchi.xyz
.. _here: https://docs.google.com/presentation/d/1PefouoeMVd27p2OGDfNQpx18mY-Wk5l0P1Ke2Vt5LwA/edit?usp=sharing

Legacy Storage
==============

.. note::

   Ceilometer's native database capabilities is intended for post processing
   and auditing purposes where responsiveness is not a requirement. It
   captures the full fidelity of each datapoint and thus is not designed
   for low latency use cases. For more responsive use cases, it's recommended
   to store data in an alternative source such as Gnocchi_. Please see
   `Moving from Ceilometer to Gnocchi`_ to find more information.

.. note::

   As of Liberty, alarming support, and subsequently its database, is handled
   by Aodh_.

.. note::

   As of Newton, event storage support is handled by Panko_.

.. _Aodh: http://docs.openstack.org/developer/aodh/
.. _Panko: http://docs.openstack.org/developer/panko

The following is a table indicating the status of each database drivers:

================== ============================= ===========================================
Driver             API querying                  API statistics
================== ============================= ===========================================
MongoDB            Yes                           Yes
MySQL              Yes                           Yes
PostgreSQL         Yes                           Yes
HBase              Yes                           Yes, except groupby & selectable aggregates
================== ============================= ===========================================

