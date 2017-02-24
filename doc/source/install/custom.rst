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

.. _customizing_deployment:

===================================
 Customizing Ceilometer Deployment
===================================

Notifications queues
====================

.. index::
   double: customizing deployment; notifications queues; multiple topics

By default, Ceilometer consumes notifications on the messaging bus sent to
**topics** by using a queue/pool name that is identical to the
topic name. You shouldn't have different applications consuming messages from
this queue. If you want to also consume the topic notifications with a system
other than Ceilometer, you should configure a separate queue that listens for
the same messages.

Ceilometer allows multiple topics to be configured so that the polling agent can
send the same messages of notifications to other queues. Notification agents
also use **topics** to configure which queue to listen for. If
you use multiple topics, you should configure notification agent and polling
agent separately, otherwise Ceilometer collects duplicate samples.

By default, the ceilometer.conf file is as follows::

   [oslo_messaging_notifications]
   topics = notifications

To use multiple topics, you should give ceilometer-agent-notification and
ceilometer-polling services different ceilometer.conf files. The Ceilometer
configuration file ceilometer.conf is normally locate in the /etc/ceilometer
directory. Make changes according to your requirements which may look like
the following::

For notification agent using ceilometer-notification.conf, settings like::

   [oslo_messaging_notifications]
   topics = notifications,xxx

For polling agent using ceilometer-polling.conf, settings like::

   [oslo_messaging_notifications]
   topics = notifications,foo

.. note::

   notification_topics in ceilometer-notification.conf should only have one same
   topic in ceilometer-polling.conf

Doing this, it's easy to listen/receive data from multiple internal and external services.

..  _publisher-configuration:

Using multiple publishers
=========================

.. index::
   double: customizing deployment; multiple publishers

Ceilometer allows multiple publishers to be configured in pipeline so that
data can be easily sent to multiple internal and external systems. Ceilometer
allows to set two types of pipelines. One is ``pipeline.yaml`` which is for
meters, another is ``event_pipeline.yaml`` which is for events.

By default, Ceilometer only saves event and meter data into Gnocchi_. If you
want Ceilometer to send data to other systems, instead of or in addition to
the default storage services, multiple publishers can be enabled by modifying
the Ceilometer pipeline.

Ceilometer ships multiple publishers currently. They are ``database``,
``notifier``, ``file``, ``http`` and ``gnocchi`` publishers.

.. _Gnocchi: http://gnocchi.xyz

To configure one or multiple publishers for Ceilometer, find the Ceilometer
configuration file ``pipeline.yaml`` and/or ``event_pipeline.yaml`` which is
normally located at /etc/ceilometer directory and make changes accordingly.
Your configuration file can be in a different directory.

To use multiple publishers, add multiple publisher lines in ``pipeline.yaml`` and/or
``event_pipeline.yaml`` file like the following::

   ---
   sources:
      - name: source_name
         events:
            - "*"
         sinks:
            - sink_name
   sinks:
      - name: sink_name
         transformers:
         publishers:
            - database://
            - gnocchi://
            - file://

For the Gnocchi publisher, the following configuration settings should be added
into /etc/ceilometer/ceilometer.conf::

    [dispatcher_gnocchi]
    archive_policy = low

The value specified for ``archive_policy`` should correspond to the name of an
``archive_policy`` configured within Gnocchi.

For the Gnocchi publisher backed by Swift storage, the following additional
configuration settings should be added::

    [dispatcher_gnocchi]
    filter_project = gnocchi_swift
    filter_service_activity = True

Custom pipeline
===============

The paths of all pipeline files including ``pipeline.yaml`` and ``event_pipeline.yaml``
are located to ceilometer/pipeline/data by default. And it's possible to set the
path through ``pipeline_cfg_file`` being assigned to another one in ``ceilometer.conf``.

Ceilometer allow users to customize pipeline files. Before that, copy the following
yaml files::

    $ cp ceilometer/pipeline/data/*.yaml /etc/ceilometer

Then you can add configurations according to the former section.

Efficient polling
=================

- There is an optional config called ``shuffle_time_before_polling_task``
  in ceilometer.conf. Enable this by setting an integer greater than zero to
  shuffle polling time for agents. This will add some random jitter to the time
  of sending requests to Nova or other components to avoid large number of
  requests in a short time period.
- There is an option to stream samples to minimise latency (at the
  expense of load) by setting ``batch_polled_samples`` to ``False`` in
  ``ceilometer.conf``.
