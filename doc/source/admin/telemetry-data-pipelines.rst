.. _telemetry-data-pipelines:

=============================
Data processing and pipelines
=============================

The mechanism by which data is processed is called a pipeline. Pipelines,
at the configuration level, describe a coupling between sources of data and
the corresponding sinks for publication of data. This
functionality is handled by the notification agents.

A source is a producer of data: ``samples`` or ``events``. In effect, it is a
set of notification handlers emitting datapoints for a set of matching meters
and event types.

Each source configuration encapsulates name matching and mapping
to one or more sinks for publication.

A sink, on the other hand, is a consumer of data, providing logic for
the publication of data emitted from related sources.

In effect, a sink describes a list of one or more publishers.

.. _telemetry-pipeline-configuration:

Pipeline configuration
~~~~~~~~~~~~~~~~~~~~~~

The notification agent supports two pipelines: one that handles samples and
another that handles events. The pipelines can be enabled and disabled by
setting `pipelines` option in the `[notifications]` section.

The actual configuration of each pipelines is, by default, stored in separate
configuration files: ``pipeline.yaml`` and ``event_pipeline.yaml``. The
location of the configuration files can be set by the ``pipeline_cfg_file`` and
``event_pipeline_cfg_file`` options listed in :ref:`configuring`

The meter pipeline definition looks like:

.. code-block:: yaml

   ---
   sources:
     - name: 'source name'
       meters:
         - 'meter filter'
       sinks:
         - 'sink name'
   sinks:
     - name: 'sink name'
       publishers:
         - 'list of publishers'

There are several ways to define the list of meters for a pipeline
source. The list of valid meters can be found in :ref:`telemetry-measurements`.
There is a possibility to define all the meters, or just included or excluded
meters, with which a source should operate:

-  To include all meters, use the ``*`` wildcard symbol. It is highly
   advisable to select only the meters that you intend on using to avoid
   flooding the metering database with unused data.

-  To define the list of meters, use either of the following:

   -  To define the list of included meters, use the ``meter_name``
      syntax.

   -  To define the list of excluded meters, use the ``!meter_name``
      syntax.

.. note::

   The OpenStack Telemetry service does not have any duplication check
   between pipelines, and if you add a meter to multiple pipelines then it is
   assumed the duplication is intentional and may be stored multiple
   times according to the specified sinks.

The above definition methods can be used in the following combinations:

-  Use only the wildcard symbol.

-  Use the list of included meters.

-  Use the list of excluded meters.

-  Use wildcard symbol with the list of excluded meters.

.. note::

   At least one of the above variations should be included in the
   meters section. Included and excluded meters cannot co-exist in the
   same pipeline. Wildcard and included meters cannot co-exist in the
   same pipeline definition section.

The publishers section contains the list of publishers, where the
samples data should be sent.

Similarly, the event pipeline definition looks like:

.. code-block:: yaml

   ---
   sources:
     - name: 'source name'
       events:
         - 'event filter'
       sinks:
         - 'sink name'
   sinks:
     - name: 'sink name'
       publishers:
         - 'list of publishers'

The event filter uses the same filtering logic as the meter pipeline.

.. _publishing:

Publishers
----------

The Telemetry service provides several transport methods to transfer the
data collected to an external system. The consumers of this data are widely
different, like monitoring systems, for which data loss is acceptable and
billing systems, which require reliable data transportation. Telemetry provides
methods to fulfill the requirements of both kind of systems.

The publisher component makes it possible to save the data into persistent
storage through the message bus or to send it to one or more external
consumers. One chain can contain multiple publishers.

To solve this problem, the multi-publisher can
be configured for each data point within the Telemetry service, allowing
the same technical meter or event to be published multiple times to
multiple destinations, each potentially using a different transport.

The following publisher types are supported:

gnocchi (default)
`````````````````

When the gnocchi publisher is enabled, measurement and resource information is
pushed to gnocchi for time-series optimized storage. Gnocchi must be registered
in the Identity service as Ceilometer discovers the exact path via the Identity
service.

More details on how to enable and configure gnocchi can be found on its
`official documentation page <https://gnocchi.osci.io>`__.

prometheus
``````````

Metering data can be send to the `pushgateway
<https://github.com/prometheus/pushgateway>`__ of Prometheus by using:

``prometheus://pushgateway-host:9091/metrics/job/openstack-telemetry``

With this publisher, timestamp are not sent to Prometheus due to Prometheus
Pushgateway design. All timestamps are set at the time it scrapes the metrics
from the Pushgateway and not when the metric was polled on the OpenStack
services.

In order to get timeseries in Prometheus that looks like the reality (but with
the lag added by the Prometheus scrapping mechanism). The `scrape_interval` for
the pushgateway must be lower and a multiple of the Ceilometer polling
interval.

You can read more `here <https://github.com/prometheus/pushgateway#about-timestamps>`__

Due to this, this is not recommended to use this publisher for billing purpose
as timestamps in Prometheus will not be exact.

notifier
````````

The notifier publisher can be specified in the form of
``notifier://?option1=value1&option2=value2``. It emits data over AMQP using
oslo.messaging. Any consumer can then subscribe to the published topic
for additional processing.

The following customization options are available:

``per_meter_topic``
    The value of this parameter is 1. It is used for publishing the samples on
    additional ``metering_topic.sample_name`` topic queue besides the
    default ``metering_topic`` queue.

``policy``
    Used for configuring the behavior for the case, when the
    publisher fails to send the samples, where the possible predefined
    values are:

    default
        Used for waiting and blocking until the samples have been sent.

    drop
        Used for dropping the samples which are failed to be sent.

    queue
        Used for creating an in-memory queue and retrying to send the
        samples on the queue in the next samples publishing period (the
        queue length can be configured with ``max_queue_length``, where
        1024 is the default value).

``topic``
    The topic name of the queue to publish to. Setting this will override the
    default topic defined by ``metering_topic`` and ``event_topic`` options.
    This option can be used to support multiple consumers.

monasca
```````

The monasca publisher can be used to send measurements to the Monasca API,
where it will be stored with other metrics gathered by Monasca Agent. Data
is accessible through the Monasca API and be transformed like other Monasca
metrics.

The pipeline sink is specified with a ``publishers:`` element of the form
``- monasca://https://<your vip>/metrics/v2.0``

Monasca API connection information is configured in the ceilometer.conf
file in a [monasca] section::

  [monasca]
  auth_section = monasca_auth
  enable_api_pagination = True
  client_retry_interval = 60
  client_max_retries = 5
  monasca_mappings = <absolute path to monasca_field_definitions.yaml>

  [monasca_auth]
  auth_url = https://<vip to keystone instance>/identity
  auth_type = password
  username = <a Keystone user>
  password = <password for user>
  project_name = <project name, such as admin>
  project_domain_id = <project domain ID, such as default>
  user_domain_id = <user domain ID, such as default>
  verify = <path to CA bundle in PEM format>
  region_name = <region name, such as RegionOne>


.. note::
  The username specified should be for a Keystone user that has the
  ``monasca_agent`` or ``monasca_user`` role enabled. For management purposes,
  this may be the ceilometer user if the appropriate role is granted.

For more detail and history of this publisher, see the
`Ceilosca Wiki <https://wiki.openstack.org/wiki/Ceilosca>`__ and
`monasca-ceilometer README
<https://github.com/openstack/monasca-ceilometer>`__.

udp
```

This publisher can be specified in the form of ``udp://<host>:<port>/``. It
emits metering data over UDP.

file
````

The file publisher can be specified in the form of
``file://path?option1=value1&option2=value2``. This publisher
records metering data into a file.

.. note::

   If a file name and location is not specified, the ``file`` publisher
   does not log any meters, instead it logs a warning message in
   the configured log file for Telemetry.

The following options are available for the ``file`` publisher:

``max_bytes``
    When this option is greater than zero, it will cause a rollover.
    When the specified size is about to be exceeded, the file is closed and a
    new file is silently opened for output. If its value is zero, rollover
    never occurs.

``backup_count``
    If this value is non-zero, an extension will be appended to the
    filename of the old log, as '.1', '.2', and so forth until the
    specified value is reached. The file that is written and contains
    the newest data is always the one that is specified without any
    extensions.

``json``
    If this option is present, will force ceilometer to write json format
    into the file.

http
````

The Telemetry service supports sending samples to an external HTTP
target. The samples are sent without any modification. To set this
option as the notification agents' target, set ``http://`` as a publisher
endpoint in the pipeline definition files. The HTTP target should be set along
with the publisher declaration. For example, additional configuration options
can be passed in: ``http://localhost:80/?option1=value1&option2=value2``

The following options are available:

``timeout``
    The number of seconds before HTTP request times out.

``max_retries``
    The number of times to retry a request before failing.

``batch``
    If false, the publisher will send each sample and event individually,
    whether or not the notification agent is configured to process in batches.

``verify_ssl``
    If false, the ssl certificate verification is disabled.

The default publisher is ``gnocchi``, without any additional options
specified. A sample ``publishers`` section in the
``/etc/ceilometer/pipeline.yaml`` looks like the following:

.. code-block:: yaml

   publishers:
       - gnocchi://
       - udp://10.0.0.2:1234
       - notifier://?policy=drop&max_queue_length=512&topic=custom_target
