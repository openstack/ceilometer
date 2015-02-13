..
      Copyright 2012 New Dream Network, LLC (DreamHost)

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
 Areas to Contribute
=====================

The Ceilometer project maintains a list of things that need to be worked on at:
https://wiki.openstack.org/wiki/Ceilometer/RoadMap but feel free to work on
something else.

.. _plugins-and-containers:

Plugins
=======

.. index::
   double: plugins; architecture
   single: plugins; setuptools
   single: plugins; entry points

Ceilometer's architecture is based heavily on the use of plugins to
make it easy to extend to collect new sorts of data or store them in
different databases.

Although we have described a list of the metrics Ceilometer should
collect, we cannot predict all of the ways deployers will want to
measure the resources their customers use. This means that Ceilometer
needs to be easy to extend and configure so it can be tuned for each
installation. A plugin system based on `setuptools entry points`_
makes it easy to add new monitors in the collector or subagents for
polling.  In particular, Ceilometer now uses Stevedore_, and you
should put your entry point definitions in the ``entry_points.txt``
file of your Ceilometer egg.

.. _setuptools entry points: http://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins

.. _Stevedore: http://stevedore.readthedocs.org

Each daemon provides basic essential services in a framework to be
shared by the plugins, and the plugins do the specialized work.  As a
general rule, the plugins are asked to do as little work as
possible. This makes them more efficient as greenlets, maximizes code
reuse, and makes them simpler to implement.

Installing a plugin automatically activates it the next time the
ceilometer daemon starts. A global configuration option can be used to
disable installed plugins (for example, one or more of the "default"
set of plugins provided as part of the ceilometer package).

Plugins may require configuration options, so when the plugin is
loaded it is asked to add options to the global flags object, and the
results are made available to the plugin before it is asked to do any
work.

Rather than running and reporting errors or simply consuming cycles
for no-ops, plugins may disable themselves at runtime based on
configuration settings defined by other components (for example, the
plugin for polling libvirt does not run if it sees that the system is
configured using some other virtualization tool). The plugin is
asked once at startup, after it has been loaded and given the
configuration settings, if it should be enabled. Plugins should not
define their own flags for enabling or disabling themselves.

Each plugin API is defined by the namespace and an abstract base class
for the plugin instances. Plugins are not required to subclass from
the API definition class, but it is encouraged as a way to discover
API changes.

.. seealso::

   * :ref:`architecture`
   * :doc:`plugins`

Core
====

The core parts of ceilometer, not separated into a plugin, are fairly
simple but depend on code that is part of ``nova`` right now. One
project goal is to move the rest of those dependencies out of ``nova``
and into ``oslo``. Logging and RPC are already done, but
the service and manager base classes still need to move.

.. seealso::

   * https://launchpad.net/nova
   * https://launchpad.net/oslo

Testing
=======

The first version of ceilometer has extensive unit tests, but
has not seen much run-time in real environments. Setting up a copy of
ceilometer to monitor a real OpenStack installation or to perform some
load testing would be especially helpful.

.. seealso::

   * :ref:`install`
