..
      Copyright 2012 Nicolas Barcet for Canonical

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=====================
Writing Agent Plugins
=====================

This documentation gives you some clues on how to write a new agent or
plugin for Ceilometer if you wish to instrument a measurement which
has not yet been covered by an existing plugin.

Plugin Framework
================

Although we have described a list of the meters Ceilometer should
collect, we cannot predict all of the ways deployers will want to
measure the resources their customers use. This means that Ceilometer
needs to be easy to extend and configure so it can be tuned for each
installation. A plugin system based on `setuptools entry points`_
makes it easy to add new monitors in the agents.  In particular,
Ceilometer now uses Stevedore_, and you should put your entry point
definitions in the :file:`entry_points.txt` file of your Ceilometer egg.

.. _setuptools entry points: http://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins

.. _Stevedore: https://docs.openstack.org/stevedore/latest/

Installing a plugin automatically activates it the next time the
ceilometer daemon starts. Rather than running and reporting errors or
simply consuming cycles for no-ops, plugins may disable themselves at
runtime based on configuration settings defined by other components (for
example, the plugin for polling libvirt does not run if it sees that the system
is configured using some other virtualization tool). Additionally, if no
valid resources can be discovered the plugin will be disabled.

Polling Agents
==============

The polling agent is implemented in :file:`ceilometer/polling/manager.py`. As
you will see in the manager, the agent loads all plugins defined in
the ``ceilometer.poll.*`` and ``ceilometer.builder.poll.*`` namespaces, then
periodically calls their :func:`get_samples` method.

Currently we keep separate namespaces - ``ceilometer.poll.compute``
and ``ceilometer.poll.central`` for quick separation of what to poll depending
on where is polling agent running. For example, this will load, among others,
the :class:`ceilometer.compute.pollsters.instance_stats.CPUPollster`

Pollster
--------

All pollsters are subclasses of
:class:`ceilometer.polling.plugin_base.PollsterBase` class. Pollsters must
implement one method: ``get_samples(self, manager, cache, resources)``, which
returns a sequence of ``Sample`` objects as defined in the
:file:`ceilometer/sample.py` file.

Compute plugins are defined as subclasses of the
:class:`ceilometer.compute.pollsters.GenericComputePollster` class as defined
in the :file:`ceilometer/compute/pollsters/__init__.py` file.

For example, in the ``CPUPollster`` plugin, the ``get_samples`` method takes
in a given list of resources representing instances on the local host, loops
through them and retrieves the `cpu time` details from resource. Similarly,
other metrics are built by pulling the appropriate value from the given list
of resources.

Notifications
=============

Notifications in OpenStack are consumed by the notification agent and passed
through `pipelines` to be normalised and re-published to specified targets.

The existing normalisation pipelines are defined in the namespace
``ceilometer.notification.pipeline``.

Each normalisation pipeline are defined as subclass of
:class:`ceilometer.pipeline.base.PipelineManager` which interprets and builds
pipelines based on a given configuration file. Pipelines are required to define
`Source` and `Sink` permutations to describe how to process notification.
Additionally, it must set ``get_main_endpoints`` which provides endpoints to be
added to the main queue listener in the notification agent. This main queue
endpoint inherits :class:`ceilometer.pipeline.base.NotificationEndpoint`
and defines which notification priorities to listen, normalises the data,
and redirects the data for pipeline processing.

Notification endpoints should implement:

``event_types``
   A sequence of strings defining the event types the endpoint should handle

``process_notifications(self, priority, notifications)``
   Receives an event message from the list provided to ``event_types`` and
   returns a sequence of objects. Using the SampleEndpoint, it should yield
   ``Sample`` objects as defined in the :file:`ceilometer/sample.py` file.

Two pipeline configurations exist and can be found under
``ceilometer.pipeline.*``. The `sample` pipeline loads in multiple endpoints
defined in ``ceilometer.sample.endpoint`` namespace. Each of the endpoints
normalises a given notification into different samples.
