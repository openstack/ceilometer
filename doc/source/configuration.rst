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

=======================
 Configuration Options
=======================

For the list and description of configuration options that can be set for Ceilometer in
order to set up the services please see the
`Telemetry section <http://docs.openstack.org/trunk/config-reference/content/ch_configuring-openstack-telemetry.html>`_
in the OpenStack Manuals Configuration Reference.

HBase
===================

This storage implementation uses Thrift HBase interface. The default Thrift
connection settings should be changed to support using ConnectionPool in HBase.
To ensure proper configuration, please add the following lines to the
`hbase-site.xml` configuration file::

    <property>
      <name>hbase.thrift.minWorkerThreads</name>
      <value>200</value>
    </property>

For pure development purposes, you can use HBase from Apache_ or some other
vendor like Cloudera or Hortonworks. To verify your installation, you can use
the `list` command in `HBase shell`, to list the tables in your
HBase server, as follows::

    $ ${HBASE_HOME}/bin/hbase shell

    hbase> list

.. note::
    This driver has been tested against HBase 0.94.2/CDH 4.2.0,
    HBase 0.94.4/HDP 1.2, HBase 0.94.18/Apache, HBase 0.94.5/Apache,
    HBase 0.96.2/Apache and HBase 0.98.0/Apache.
    Versions earlier than 0.92.1 are not supported due to feature incompatibility.

To find out more about supported storage backends please take a look on the
:doc:`install/manual/` guide.

.. note::

    If you are changing the configuration on the fly to use HBase, as a storage
    backend, you will need to restart the Ceilometer services that use the
    database to allow the changes to take affect, i.e. the collector and API
    services.

.. _Apache: https://hbase.apache.org/book/quickstart.html


Sample Configuration file
=========================

The sample configuration file for Ceilometer, named
etc/ceilometer/ceilometer.conf.sample, was removed from version control after
the Icehouse release. For more details, please read the file
etc/ceilometer/README-ceilometer.conf.txt. You can generate this sample
configuration file by running ``tox -e genconfig``.

.. note::
    tox version 1.7.0 and 1.7.1 have a `backward compatibility issue`_
    with OpenStack projects. If you meet the "tox.ConfigError: ConfigError:
    substitution key 'posargs' not found" problem, run
    ``sudo pip install -U "tox>=1.6.1,!=1.7.0,!=1.7.1"`` to get a proper
    version, then try ``tox -e genconfig`` again.

.. _`backward compatibility issue`: https://bitbucket.org/hpk42/tox/issue/150/posargs-configerror

.. _Pipeline-Configuration:

Pipelines
=========

Pipelines describe a coupling between sources of samples and the
corresponding sinks for transformation and publication of the samples.

A source is a producer of samples, in effect a set of pollsters and/or
notification handlers emitting samples for a set of matching meters.
See :doc:`plugins` for details on how to write and plug in your plugins.

Each source configuration encapsulates meter name matching, polling
interval determination, optional resource enumeration or discovery,
and mapping to one or more sinks for publication.

A sink on the other hand is a consumer of samples, providing logic for
the transformation and publication of samples emitted from related sources.
Each sink configuration is concerned `only` with the transformation rules
and publication conduits for samples.

In effect, a sink describes a chain of handlers. The chain starts with
zero or more transformers and ends with one or more publishers. The first
transformer in the chain is passed samples from the corresponding source,
takes some action such as deriving rate of change, performing unit conversion,
or aggregating, before passing the modified sample to next step.

The chains end with one or more publishers. This component makes it possible
to persist the data into storage through the message bus or to send it to one
or more external consumers. One chain can contain multiple publishers, see the
:ref:`multi-publisher` section.


Pipeline configuration
----------------------

Pipeline configuration by default, is stored in a separate configuration file,
called pipeline.yaml, next to the ceilometer.conf file. The pipeline
configuration file can be set in the *pipeline_cfg_file* parameter in
ceilometer.conf. Multiple chains can be defined in one configuration file.

The chain definition looks like the following::

    ---
    sources:
      - name: 'source name'
        interval: 'how often should the samples be injected into the pipeline'
        meters:
          - 'meter filter'
        resources:
          - 'list of resource URLs'
        discovery:
          - 'list of discoverers'
        sinks
          - 'sink name'
    sinks:
      - name: 'sink name'
        transformers: 'definition of transformers'
        publishers:
          - 'list of publishers'

The *name* parameter of a source is unrelated to anything else;
nothing references a source by name, and a source's name does not have
to match anything.

The *interval* parameter in the sources section should be defined in seconds. It
determines the cadence of sample injection into the pipeline, where samples are
produced under the direct control of an agent, i.e. via a polling cycle as opposed
to incoming notifications.

There are several ways to define the list of meters for a pipeline source. The
list of valid meters can be found in the :ref:`measurements` section. There is
a possibility to define all the meters, or just included or excluded meters,
with which a source should operate:

* To include all meters, use the '*' wildcard symbol.
* To define the list of meters, use either of the following:

  * To define the list of included meters, use the 'meter_name' syntax
  * To define the list of excluded meters, use the '!meter_name' syntax
  * For meters, which identify a complex Sample field, use the wildcard
    symbol to select all, e.g. for "disk.read.bytes", use "disk.\*"

The above definition methods can be used in the following combinations:

* Only the wildcard symbol
* The list of included meters
* The list of excluded meters
* Wildcard symbol with the list of excluded meters

.. note::
    At least one of the above variations should be included in the meters
    section. Included and excluded meters cannot co-exist in the same
    pipeline. Wildcard and included meters cannot co-exist in the same
    pipeline definition section.

A given polling plugin is invoked according to each source section
whose *meters* parameter matches the plugin's meter name.  That is,
the matching source sections are combined by union, not intersection,
of the prescribed time series.

The optional *resources* section of a pipeline source allows a list of
static resource URLs to be configured. An amalgamated list of all
statically configured resources for a set of pipeline sources with a
common interval is passed to individual pollsters matching those pipelines.

The optional *discovery* section of a pipeline source contains the list of
discoverers. These discoverers can be used to dynamically discover the
resources to be polled by the pollsters defined in this pipeline. The name
of the discoverers should be the same as the related names of plugins in
setup.cfg.

If *resources* or *discovery* section is not set, the default value would
be an empty list. If both *resources* and *discovery* are set, the final
resources passed to the pollsters will be the combination of the dynamic
resources returned by the discoverers and the static resources defined
in the *resources* section. If there are some duplications between the
resources returned by the discoverers and those defined in the *resources*
section, the duplication will be removed before passing those resources
to the pollsters.

There are three ways a pollster can get a list of resources to poll, as the
following in descending order of precedence:

    1. From the per-pipeline configured discovery and/or static resources.
    2. From the per-pollster default discovery.
    3. From the per-agent default discovery.

The *transformers* section of a pipeline sink provides the possibility to add a
list of transformer definitions. The names of the transformers should be the same
as the names of the related extensions in setup.cfg. For a more detailed
description, please see the `transformers`_ section of the Administrator Guide
of Ceilometer.

.. _transformers: http://docs.openstack.org/admin-guide-cloud/telemetry-data-collection.html#transformers

The *publishers* section contains the list of publishers, where the samples
data should be sent after the possible transformations. The names of the
publishers should be the same as the related names of the plugins in
setup.cfg.

The default configuration can be found in `pipeline.yaml`_.

.. _pipeline.yaml: https://git.openstack.org/cgit/openstack/ceilometer/tree/etc/ceilometer/pipeline.yaml

Publishers
++++++++++

For more information about publishers see the `publishers`_ section of the
Administrator Guide of Ceilometer.

.. _publishers: http://docs.openstack.org/admin-guide-cloud/telemetry-data-retrieval.html#publishers
