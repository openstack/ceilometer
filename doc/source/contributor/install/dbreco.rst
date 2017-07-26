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

Ceilometer is a data collection service. It normalizes data across OpenStack
and can be configured to persist the normalized data to multiple services.
Gnocchi_ is designed to store time-series **measurement data**. Panko_ is
intended to capture **event data**. Lastly, Aodh_ provides **alarming**
functionality.

Moving from Ceilometer to Gnocchi
=================================

Gnocchi represents a fundamental change in how data is represented and stored.
Installation and configuration can be found in :ref:`installing_manually`.
Differences between APIs can be found here_.

There currently exists no migration tool between the services. To transition
to Gnocchi, multiple publishers can be enabled in the Collector to capture
data in both the native Ceilometer database and Gnocchi. This will allow you
to test Gnocchi and transition to it fully when comfortable. Edit the
``pipeline.yaml`` and ``event_pipeline.yaml`` to include multiple publishers::

  ---
  sources:
      - name: event_source
        events:
            - "*"
        sinks:
            - event_sink
  sinks:
      - name: event_sink
        publishers:
            - gnocchi://
            - database://

.. _Gnocchi: http://gnocchi.xyz
.. _Aodh: https://docs.openstack.org/aodh/latest/
.. _Panko: https://docs.openstack.org/panko/latest/
.. _here: https://www.slideshare.net/GordonChung/ceilometer-to-gnocchi
