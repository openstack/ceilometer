..
      Copyright 2012 New Dream Network (DreamHost)
      Copyright 2013 eNovance

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

==========
 Glossary
==========

.. glossary::

   agent
     Software service running on the OpenStack infrastructure
     measuring usage and sending the results to the :term:`collector`.

   API server
     HTTP REST API service for ceilometer.

   billing
     Billing is the process to assemble bill line items into a single
     per customer bill, emitting the bill to start the payment collection.

   bus listener agent
     Bus listener agent which takes events generated on the Oslo
     notification bus and transforms them into Ceilometer samples. This
     is the preferred method of data collection.

   ceilometer
     From Wikipedia [#]_:

       A ceilometer is a device that uses a laser or other light
       source to determine the height of a cloud base.

   polling agent
     Software service running either on a central management node within the
     OpenStack infrastructure or compute node measuring usage and sending the
     results to the :term:`collector`.

   collector
     Software service running on the OpenStack infrastructure
     monitoring notifications from other OpenStack components and
     samples from the ceilometer agent and recording the results
     in the database.

   notification agent
     The different OpenStack services emit several notifications about the
     various types of events. The notification agent consumes them from
     respective queues and filters them by the event_type.

   data store
     Storage system for recording data collected by ceilometer.

   meter
     The measurements tracked for a resource. For example, an instance has
     a number of meters, such as duration of instance, CPU time used,
     number of disk io requests, etc.
     Three types of meters are defined in ceilometer:

       * Cumulative: Increasing over time (e.g. disk I/O)
       * Gauge: Discrete items (e.g. floating IPs, image uploads) and fluctuating
         values (e.g. number of Swift objects)
       * Delta: Incremental change to a counter over time (e.g. bandwidth delta)

   metering
     Metering is the process of collecting information about what,
     who, when and how much regarding anything that can be billed. The result of
     this is a collection of "tickets" (a.k.a. samples) which are ready to be
     processed in any way you want.

   notification
     A message sent via an external OpenStack system (e.g Nova, Glance,
     etc) using the Oslo notification mechanism [#]_. These notifications
     are usually sent to and received by Ceilometer through the notifier
     RPC driver.

   non-repudiable
    From Wikipedia [#]_:

      Non-repudiation refers to a state of affairs where the purported
      maker of a statement will not be able to successfully challenge
      the validity of the statement or contract. The term is often
      seen in a legal setting wherein the authenticity of a signature
      is being challenged. In such an instance, the authenticity is
      being "repudiated".

   project
     The OpenStack tenant or project.

   polling agents
     The polling agent is collecting measurements by polling some API or other
     tool at a regular interval.

   push agents
     The push agent is the only solution to fetch data within projects,
     which do not expose the required data in a remotely usable way. This
     is not the preferred method as it makes deployment a bit more
     complex having to add a component to each of the nodes that need
     to be monitored.

   rating
     Rating is the process of analysing a series of tickets,
     according to business rules defined by marketing, in order to transform
     them into bill line items with a currency value.

   resource
     The OpenStack entity being metered (e.g. instance, volume, image, etc).

   sample
     Data sample for a particular meter.

   source
     The origin of metering data. This field is set to "openstack" by default.
     It can be configured to a different value using the sample_source field
     in the ceilometer.conf file.

   user
     An OpenStack user.

.. [#] http://en.wikipedia.org/wiki/Ceilometer
.. [#] https://git.openstack.org/cgit/openstack/ceilometer/tree/ceilometer/openstack/common/notifier
.. [#] http://en.wikipedia.org/wiki/Non-repudiation
