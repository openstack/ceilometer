.. -*- rst -*-

============
Capabilities
============

Gets information for API and storage capabilities.

The Telemetry service enables you to store samples, events, and
alarm definitions in supported database back ends. The
``capabilities`` resource enables you to list the capabilities that
a database supports.

The ``capabilities`` resource returns a flattened dictionary of
capability properties, each with an associated boolean value. A
value of ``true`` indicates that the corresponding capability is
available in the back end.

You can optionally configure separate database back ends for
samples, events, and alarms definitions. The ``capabilities``
response shows a value of ``true`` to indicate that the definitions
database for samples, events, or alarms is ready to use in a
production environment.


List capabilities
=================

.. rest_method::  GET /v2/capabilities

A representation of the API and storage capabilities. Usually, the storage driver imposes constraints.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml



Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - statistics:query:complex: statistics:query:complex
   - alarms:history:query:simple: alarms:history:query:simple
   - meters:query:metadata: meters:query:metadata
   - alarms:query:simple: alarms:query:simple
   - resources:query:simple: resources:query:simple
   - api: api
   - statistics:aggregation:selectable:quartile: statistics:aggregation:selectable:quartile
   - statistics:query:simple: statistics:query:simple
   - statistics:aggregation:selectable:count: statistics:aggregation:selectable:count
   - statistics:aggregation:selectable:min: statistics:aggregation:selectable:min
   - statistics:aggregation:selectable:sum: statistics:aggregation:selectable:sum
   - storage: storage
   - alarm_storage: alarm_storage
   - statistics:aggregation:selectable:avg: statistics:aggregation:selectable:avg
   - meters:query:complex: meters:query:complex
   - statistics:groupby: statistics:groupby
   - alarms:history:query:complex: alarms:history:query:complex
   - meters:query:simple: meters:query:simple
   - samples:query:metadata: samples:query:metadata
   - statistics:query:metadata: statistics:query:metadata
   - storage:production_ready: storage:production_ready
   - samples:query:simple: samples:query:simple
   - resources:query:metadata: resources:query:metadata
   - statistics:aggregation:selectable:max: statistics:aggregation:selectable:max
   - samples:query:complex: samples:query:complex
   - statistics:aggregation:standard: statistics:aggregation:standard
   - events:query:simple: events:query:simple
   - statistics:aggregation:selectable:stddev: statistics:aggregation:selectable:stddev
   - alarms:query:complex: alarms:query:complex
   - statistics:aggregation:selectable:cardinality: statistics:aggregation:selectable:cardinality
   - event_storage: event_storage
   - resources:query:complex: resources:query:complex



Response Example
----------------

.. literalinclude:: ../samples/capabilities-list-response.json
   :language: javascript



