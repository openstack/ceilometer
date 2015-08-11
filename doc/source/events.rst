..
      Copyright 2013 Rackspace Hosting.

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _events:

=============================
 Events and Event Processing
=============================

Events vs. Samples
==================

In addition to Meters, and related Sample data, Ceilometer can also process
Events.  While a Sample represents a single numeric datapoint, driving a Meter
that represents the changes in that value over time, an Event represents the
state of an object in an OpenStack service (such as an Instance in Nova, or
an Image in Glance) at a point in time when something of interest has occurred.
This can include non-numeric data, such as an instance's flavor, or network
address.

In general, Events let you know when something has changed about an
object in an OpenStack system, such as the resize of an instance, or creation
of an image.

While Samples can be relatively cheap (small),
disposable (losing an individual sample datapoint won't matter much),
and fast, Events are larger, more informative, and should be handled more
consistently (you do not want to lose one).

Event Structure
===============

To facilitate downstream processing (billing and/or aggregation), a
:doc:`minimum required data set and format <format>` has been defined for
services, however events generally contain the following information:


event_type
    A dotted string defining what event occurred, such as "compute.instance.resize.start"

message_id
    A UUID for this event.

generated
    A timestamp of when the event occurred on the source system.

traits
    A flat mapping of key-value pairs.
    The event's Traits contain most of the details of the event. Traits are
    typed, and can be strings, ints, floats, or datetimes.

raw
    (Optional) Mainly for auditing purpose, the full notification message
    can be stored (unindexed) for future evaluation.

Events from Notifications
=========================

Events are primarily created via the notifications system in OpenStack.
OpenStack systems, such as Nova, Glance, Neutron, etc. will emit
notifications in a JSON format to the message queue when some notable action is
taken by that system. Ceilometer will consume such notifications from the
message queue, and process them.

The general philosophy of notifications in OpenStack is to emit any and all
data someone might need, and let the consumer filter out what they are not
interested in. In order to make processing simpler and more efficient,
the notifications are stored and processed within Ceilometer as Events.
The notification payload, which can be an arbitrarily complex JSON data
structure, is converted to a flat set of key-value pairs known as Traits.
This conversion is specified by a config file, so that only the specific
fields within the notification that are actually needed for processing the
event will have to be stored as Traits.

Note that the Event format is meant for efficient processing and querying,
there are other means available for archiving notifications (i.e. for audit
purposes, etc), possibly to different datastores.

Converting Notifications to Events
----------------------------------

In order to make it easier to allow users to extract what they need,
the conversion from Notifications to Events is driven by a
configuration file (specified by the flag definitions_cfg_file_ in
ceilometer.conf).

This includes descriptions of how to map fields in the notification body
to Traits, and optional plugins for doing any programmatic translations
(splitting a string, forcing case, etc.)

The mapping of notifications to events is defined per event_type, which
can be wildcarded. Traits are added to events if the corresponding fields
in the notification exist and are non-null. (As a special case, an empty
string is considered null for non-text traits. This is due to some openstack
projects (mostly Nova) using empty string for null dates.)

If the definitions file is not present, a warning will be logged, but an empty
set of definitions will be assumed. By default, any notifications that
do not have a corresponding event definition in the definitions file will be
converted to events with a set of minimal, default traits.  This can be
changed by setting the flag drop_unmatched_notifications_ in the
ceilometer.conf file. If this is set to True, then any notifications
that don't have events defined for them in the file will be dropped.
This can be what you want, the notification system is quite chatty by design
(notifications philosophy is "tell us everything, we'll ignore what we don't
need"), so you may want to ignore the noisier ones if you don't use them.

.. _definitions_cfg_file: http://docs.openstack.org/trunk/config-reference/content/ch_configuring-openstack-telemetry.html
.. _drop_unmatched_notifications: http://docs.openstack.org/trunk/config-reference/content/ch_configuring-openstack-telemetry.html

There is a set of default traits (all are TEXT type) that will be added to
all events if the notification has the relevant data:

* service:  (All notifications should have this) notification's publisher
* tenant_id
* request_id
* project_id
* user_id

These do not have to be specified in the event definition, they are
automatically added, but their definitions can be overridden for a given
event_type.

Definitions file format
-----------------------

The event definitions file is in YAML format. It consists of a list of event
definitions, which are mappings. Order is significant, the list of definitions
is scanned in *reverse* order (last definition in the file to the first),
to find a definition which matches the notification's event_type.  That
definition will be used to generate the Event. The reverse ordering is done
because it is common to want to have a more general wildcarded definition
(such as "compute.instance.*" ) with a set of traits common to all of those
events, with a few more specific event definitions (like
"compute.instance.exists") afterward that have all of the above traits, plus
a few more. This lets you put the general definition first, followed by the
specific ones, and use YAML mapping include syntax to avoid copying all of the
trait definitions.

Event Definitions
-----------------

Each event definition is a mapping with two keys (both required):

event_type
    This is a list (or a string, which will be taken as a 1 element
    list) of event_types this definition will handle. These can be
    wildcarded with unix shell glob syntax. An exclusion listing
    (starting with a '!') will exclude any types listed from matching.
    If ONLY exclusions are listed, the definition will match anything
    not matching the exclusions.
traits
    This is a mapping, the keys are the trait names, and the values are
    trait definitions.

Trait Definitions
-----------------

Each trait definition is a mapping with the following keys:

type
    (optional) The data type for this trait. (as a string). Valid
    options are: *text*, *int*, *float*, and *datetime*.
    defaults to *text* if not specified.
fields
    A path specification for the field(s) in the notification you wish
    to extract for this trait. Specifications can be written to match
    multiple possible fields, the value for the trait will be derived
    from the matching fields that exist and have a non-null values in
    the notification. By default the value will be the first such field.
    (plugins can alter that, if they wish). This is normally a string,
    but, for convenience, it can be specified as a list of
    specifications, which will match the fields for all of them. (See
    `Field Path Specifications`_ for more info on this syntax.)
plugin
    (optional) This is a mapping (For convenience, this value can also
    be specified as a string, which is interpreted as the name of a
    plugin to be loaded with no parameters) with the following keys

    name
        (string) name of a plugin to load

    parameters
        (optional) Mapping of keyword arguments to pass to the plugin on
        initialization. (See documentation on each plugin to see what
        arguments it accepts.)

Field Path Specifications
-------------------------

The path specifications define which fields in the JSON notification
body are extracted to provide the value for a given trait.  The paths
can be specified with a dot syntax (e.g. "payload.host"). Square
bracket syntax (e.g. "payload[host]") is also supported. In either
case, if the key for the field you are looking for contains special
characters, like '.', it will need to be quoted (with double or single
quotes) like so:

          payload.image_meta.'org.openstack__1__architecture'

The syntax used for the field specification is a variant of JSONPath,
and is fairly flexible. (see: https://github.com/kennknowles/python-jsonpath-rw for more info)

Example Definitions file
------------------------

::

    ---
    - event_type: compute.instance.*
      traits: &instance_traits
        user_id:
          fields: payload.user_id
        instance_id:
          fields: payload.instance_id
        host:
          fields: publisher_id
          plugin:
            name: split
            parameters:
              segment: 1
              max_split: 1
        service_name:
          fields: publisher_id
          plugin: split
        instance_type_id:
          type: int
          fields: payload.instance_type_id
        os_architecture:
          fields: payload.image_meta.'org.openstack__1__architecture'
        launched_at:
          type: datetime
          fields: payload.launched_at
        deleted_at:
          type: datetime
          fields: payload.deleted_at
    - event_type:
        - compute.instance.exists
        - compute.instance.update
      traits:
        <<: *instance_traits
        audit_period_beginning:
          type: datetime
          fields: payload.audit_period_beginning
        audit_period_ending:
          type: datetime
          fields: payload.audit_period_ending

Trait plugins
-------------

Trait plugins can be used to do simple programmatic conversions on the value in
a notification field, like splitting a string, lowercasing a value, converting
a screwball date into ISO format, or the like. They are initialized with the
parameters from the trait definition, if any, which can customize their
behavior for a given trait. They are called with a list of all matching fields
from the notification, so they can derive a value from multiple fields. The
plugin will be called even if there are no fields found matching the field
path(s), this lets a plugin set a default value, if needed. A plugin can also
reject a value by returning *None*, which will cause the trait not to be
added. If the plugin returns anything other than *None*, the trait's value
will be set to whatever the plugin returned (coerced to the appropriate type
for the trait).

Building Notifications
======================

In general, the payload format OpenStack services emit could be described as
the Wild West. The payloads are often arbitrary data dumps at the time of
the event which is often susceptible to change. To make consumption easier,
the Ceilometer team offers two proposals: CADF_, an open, cloud standard
which helps model cloud events and the PaaS Event Format.

.. toctree::
   :maxdepth: 1

   format

.. _CADF: http://docs.openstack.org/developer/pycadf/
