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

.. _plugins-and-containers:

=======================
 Writing Agent Plugins
=======================

This documentation gives you some clues on how to write a new agent or
plugin for Ceilometer if you wish to instrument a measurement which
has not yet been covered by an existing plugin.

Agents
======

Polling agent might be run either on central cloud management nodes or on the
compute nodes (where direct hypervisor polling is quite logical).

The agent running on each compute node polls for compute resources
usage. Each meter collected is tagged with the resource ID (such as
an instance) and the owner, including tenant and user IDs. The meters
are then reported to the collector via the message bus. More detailed
information follows.

The agent running on the cloud central management node polls other types of
resources from a management server (usually using OpenStack services API to
collect this data).

The polling agent is implemented in ``ceilometer/agent/manager.py``. As
you will see in the manager, the agent loads all plugins defined in
the namespace ``ceilometer.poll.agent``, then periodically calls their
:func:`get_samples` method.

Plugins
=======

A polling agent can support multiple plugins to retrieve different
information and send them to the collector. As stated above, an agent
will automatically activate all possible plugins if no additional information
about what to poll was passed. Previously we had separated compute and
central agents with different namespaces with plugins (pollsters) defined
within. Currently we keep separated namespaces - ``ceilometer.poll.compute``
and ``ceilometer.poll.central`` for quick separation of what to poll depending
on where is polling agent running.  This will load, among others, the
:class:`ceilometer.compute.pollsters.cpu.CPUPollster`, which is defined in
the folder ``ceilometer/compute/pollsters``.

Notifications mechanism uses plugins as well, for instance
:class:`ceilometer.telemetry.notifications.TelemetryApiPost` plugin
which is defined in the ``ceilometer/telemetry/notifications`` folder, Though
in most cases, this is not needed. A meter definition can be directly added
to :file:`ceilometer/meter/data/meter.yaml` to match the event type. For
more information, see the :ref:`add_new_meters` page.

We are using these two existing plugins as examples as the first one provides
an example of how to interact when you need to retrieve information from an
external system (pollster) and the second one is an example of how to forward
an existing event notification on the standard OpenStack queue to ceilometer.

Pollster
--------

Compute plugins are defined as subclasses of the
:class:`ceilometer.compute.BaseComputePollster` class as defined in
the ``ceilometer/compute/__init__.py`` file. Pollsters must implement one
method: ``get_samples(self, manager, context)``, which returns a
sequence of ``Sample`` objects as defined in the
``ceilometer/sample.py`` file.

In the ``CPUPollster`` plugin, the ``get_samples`` method is implemented as a
loop which, for each instances running on the local host, retrieves the
cpu_time from the hypervisor and sends back two ``Sample`` objects.  The first
one, named "cpu", is of type "cumulative", meaning that between two polls, its
value is not reset while the instance remains active, or in other words that
the CPU value is always provided as a duration that continuously increases
since the creation of the instance. The second one, named "cpu_util", is of
type "gauge", meaning that its value is the percentage of cpu utilization.

Note that the ``LOG`` method is only used as a debugging tool and does not
participate in the actual metering activity.

There is the way to specify either namespace(s) with pollsters or just
list of concrete pollsters to use, or even both of these parameters on the
polling agent start via CLI parameter:

    ceilometer-polling --polling-namespaces central compute

This command will basically make polling agent to load all plugins from the
central and compute namespaces and poll everything it can. If you need to load
only some of the pollsters, you can use ``pollster-list`` option:

    ceilometer-polling --pollster-list image image.size storage.*

If both of these options are passed, the polling agent will load only those
pollsters specified in the pollster list, that can be loaded from the selected
namespaces.

.. note::

   Agents coordination cannot be used in case of pollster-list option usage.
   This allows to avoid both samples duplication and their lost.

Notifications
-------------

.. note::
   This should only be needed for cases where a complex arithmetic or
   non-primitive data types are used. In most cases, adding a meter
   definition to the :file:`ceilometer/meter/data/meter.yaml` should
   suffice.

Notifications are defined as subclass of the
:class:`ceilometer.agent.plugin_base.NotificationBase` meta class.
Notifications must implement:

   ``event_types`` which should be a sequence of strings defining the event types to be given to the plugin and

   ``process_notification(self, message)`` which receives an event message from the list provided to event_types and returns a sequence of Sample objects as defined in the ``ceilometer/sample.py`` file.

In the ``InstanceNotifications`` plugin, it listens to three events:

* compute.instance.create.end

* compute.instance.exists

* compute.instance.delete.start

using the ``get_event_type`` method and subsequently the method
``process_notification`` will be invoked each time such events are happening which
generates the appropriate sample objects to be sent to the collector.

Adding new plugins
------------------

Although we have described a list of the meters Ceilometer should
collect, we cannot predict all of the ways deployers will want to
measure the resources their customers use. This means that Ceilometer
needs to be easy to extend and configure so it can be tuned for each
installation. A plugin system based on `setuptools entry points`_
makes it easy to add new monitors in the agents.  In particular,
Ceilometer now uses Stevedore_, and you should put your entry point
definitions in the ``entry_points.txt`` file of your Ceilometer egg.

.. _setuptools entry points: http://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins

.. _Stevedore: http://stevedore.readthedocs.org

Installing a plugin automatically activates it the next time the
ceilometer daemon starts. Rather than running and reporting errors or
simply consuming cycles for no-ops, plugins may disable themselves at
runtime based on configuration settings defined by other components (for example, the
plugin for polling libvirt does not run if it sees that the system is
configured using some other virtualization tool). Additionally, if no
valid resources can be discovered the plugin will be disabled.


Tests
=====
Any new plugin or agent contribution will only be accepted into the project if
provided together with unit tests.  Those are defined for the compute agent
plugins in the directory ``tests/compute`` and for the agent itself in ``test/agent``.
Unit tests are run in a continuous integration process for each commit made to
the project, thus ensuring as best as possible that a given patch has no side
effect to the rest of the project.
