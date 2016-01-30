..
      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _upgrade:

==========
 Upgrading
==========

Ceilometer's services support both full upgrades as well as partial
(rolling) upgrades. The required steps for each process are described below.


Full upgrades
=============

The following describes how to upgrade your entire Ceilometer environment in
one pass.

.. _full upgrade path:

1. Upgrade the database (if applicable)

   Run ceilometer-dbsync to upgrade the database if using one of Ceilometer's
   databases (see :ref:`choosing_db_backend`). The database does not need to be
   taken offline as no data is modified or deleted. Ideally this should be done
   during a period of low activity. Best practices should still be followed
   (ie. back up your data). If not using a Ceilometer database, you should
   consult the documentation of that storage beforehand.

2. Upgrade the collector service(s)

   Shutdown all collector services. The new collector, that knows how to
   interpret the new payload, can then be started. It will disregard any
   historical attributes and can continue to process older data from the
   agents. You may restart as many new collectors as required.

3. Upgrade the notification agent(s)

   The notification agent can then be taken offline and upgraded with the
   same conditions as the collector service.

4. Upgrade the polling agent(s)

   In this path, you'll want to take down agents on all hosts before starting.
   After starting the first agent, you should verify that data is again being
   polled. Additional agents can be added to support coordination if enabled.

.. note::

   The API service can be taken offline and upgraded at any point in the
   process (if applicable).


Partial upgrades
================

The following describes how to upgrade parts of your Ceilometer environment
gradually. The ultimate goal is to have all services upgraded to the new
version in time.

1. Upgrade the database (if applicable)

   Upgrading the database here is the same as the `full upgrade path`_.

2. Upgrade the collector service(s)

   The new collector services can be started alongside the old collectors.
   Collectors old and new will disregard any new or historical attributes.

3. Upgrade the notification agent(s)

   The new notification agent can be started alongside the old agent if no
   workload_partioning is enabled OR if it has the same pipeline configuration.
   If the pipeline configuration is changed, the old agents must be loaded with
   the same pipeline configuration first to ensure the notification agents all
   work against same pipeline sets.

4. Upgrade the polling agent(s)

   The new polling agent can be started alongside the old agent only if no new
   pollsters were added. If not, new polling agents must start only in it's
   own partitioning group and poll only the new pollsters. After all old agents
   are upgraded, the polling agents can be changed to poll both new pollsters
   AND the old ones.

5. Upgrade the API service(s)

   API management is handled by WSGI so there is only ever one version of API
   service running

.. note::

   Upgrade ordering does not matter in partial upgrade path. The only
   requirement is that the database be upgraded first. It is advisable to
   upgrade following the same ordering as currently described: database,
   collector, notification agent, polling agent, api.


Developer notes
===============

When updating data models in the database or IPC, we need to adhere to a single
mantra: 'always add, never delete or modify.'
