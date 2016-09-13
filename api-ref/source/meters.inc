.. -*- rst -*-

======
Meters
======

Lists all meters, adds samples to meters, and lists samples for
meters. For list operations, if you do not explicitly set the
``limit`` query parameter, a default limit is applied. The default
limit is the ``default_api_return_limit`` configuration option
value.

Also, computes and lists statistics for samples in a time range.
You can use the ``aggregate`` query parameter in the ``statistics``
URI to explicitly select the ``stddev``, ``cardinality``, or any
other standard function. For example:

::

   GET /v2/meters/METER_NAME/statistics?aggregate.func=NAME
   &
   aggregate.param=VALUE

The ``aggregate.param`` parameter value is optional for all
functions except the ``cardinality`` function.

The API silently ignores any duplicate aggregate function and
parameter pairs.

The API accepts and storage drivers support duplicate functions
with different parameter values. In this example, the
``cardinality`` function is accepted twice with two different
parameter values:

::

   GET /v2/meters/METER_NAME/statistics?aggregate.func=cardinality
   &
   aggregate.param=resource_id
           &
   aggregate.func=cardinality
   &
   aggregate.param=project_id

**Examples:**

Use the ``stddev`` function to request the standard deviation of
CPU utilization:

::

   GET /v2/meters/cpu_util/statistics?aggregate.func=stddev

The response looks like this:

.. code-block:: json

   [
       {
           "aggregate": {
               "stddev": 0.6858829
           },
           "duration_start": "2014-01-30T11:13:23",
           "duration_end": "2014-01-31T16:07:13",
           "duration": 104030,
           "period": 0,
           "period_start": "2014-01-30T11:13:23",
           "period_end": "2014-01-31T16:07:13",
           "groupby": null,
           "unit": "%"
       }
   ]

Use the ``cardinality`` function with the project ID to return the
number of distinct tenants with images:

::

   GET /v2/meters/image/statistics?aggregate.func=cardinality
   &
   aggregate.param=project_id

The following, more complex, example determines:

- The number of distinct instances (``cardinality``)

- The total number of instance samples (``count``) for a tenant in
  15-minute intervals (``period`` and ``groupby`` options)

::

   GET /v2/meters/instance/statistics?aggregate.func=cardinality
   &
   aggregate.param=resource_id
           &
   aggregate.func=count
   &
   groupby=project_id
   &
   period=900

The response looks like this:

.. code-block:: json

   [
       {
           "count": 19,
           "aggregate": {
               "count": 19,
               "cardinality/resource_id": 3
           },
           "duration": 328.47803,
           "duration_start": "2014-01-31T10:00:41.823919",
           "duration_end": "2014-01-31T10:06:10.301948",
           "period": 900,
           "period_start": "2014-01-31T10:00:00",
           "period_end": "2014-01-31T10:15:00",
           "groupby": {
               "project_id": "061a5c91811e4044b7dc86c6136c4f99"
           },
           "unit": "instance"
       },
       {
           "count": 22,
           "aggregate": {
               "count": 22,
               "cardinality/resource_id": 4
           },
           "duration": 808.00385,
           "duration_start": "2014-01-31T10:15:15",
           "duration_end": "2014-01-31T10:28:43.003840",
           "period": 900,
           "period_start": "2014-01-31T10:15:00",
           "period_end": "2014-01-31T10:30:00",
           "groupby": {
               "project_id": "061a5c91811e4044b7dc86c6136c4f99"
           },
           "unit": "instance"
       },
       {
           "count": 2,
           "aggregate": {
               "count": 2,
               "cardinality/resource_id": 2
           },
           "duration": 0,
           "duration_start": "2014-01-31T10:35:15",
           "duration_end": "2014-01-31T10:35:15",
           "period": 900,
           "period_start": "2014-01-31T10:30:00",
           "period_end": "2014-01-31T10:45:00",
           "groupby": {
               "project_id": "061a5c91811e4044b7dc86c6136c4f99"
           },
           "unit": "instance"
       }
   ]


Show meter statistics
=====================

.. rest_method::  GET /v2/meters/{meter_name}/statistics

Computes and lists statistics for samples in a time range.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - meter_name: meter_name
   - q: q
   - groupby: groupby
   - period: period
   - aggregate: aggregate
   - limit: limit


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - count: count
   - duration_start: duration_start
   - min: min
   - max: max
   - duration_end: duration_end
   - period: period
   - sum: sum
   - duration: duration
   - period_end: period_end
   - aggregate: aggregate
   - period_start: period_start
   - avg: avg
   - groupby: groupby
   - unit: unit



Response Example
----------------

.. literalinclude:: ../samples/statistics-list-response.json
   :language: javascript




List meters
===========

.. rest_method::  GET /v2/meters

Lists meters, based on the data recorded so far.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - q: q
   - limit: limit


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - user_id: user_id
   - name: name
   - resource_id: resource_id
   - source: source
   - meter_id: meter_id
   - project_id: project_id
   - type: type
   - unit: unit



Response Example
----------------

.. literalinclude:: ../samples/meters-list-response.json
   :language: javascript




List samples for meter
======================

.. rest_method::  GET /v2/meters/{meter_name}

Lists samples for a meter, by meter name.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - meter_name: meter_name
   - q: q
   - limit: limit


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - user_id: user_id
   - resource_id: resource_id
   - timestamp: timestamp
   - meter: meter
   - volume: volume
   - source: source
   - recorded_at: recorded_at
   - project_id: project_id
   - type: type
   - id: id
   - unit: unit
   - metadata: metadata



Response Example
----------------

.. literalinclude:: ../samples/samples-list-response.json
   :language: javascript




Add samples to meter
====================

.. rest_method::  POST /v2/meters/{meter_name}

Adds samples to a meter, by meter name.

If you attempt to add a sample that is not supported, this call
returns the ``409`` response code.


Normal response codes: 200
Error response codes:409,


Request
-------

.. rest_parameters:: parameters.yaml

   - user_id: user_id
   - resource_id: resource_id
   - timestamp: timestamp
   - meter: meter
   - volume: volume
   - source: source
   - recorded_at: recorded_at
   - project_id: project_id
   - type: type
   - id: id
   - unit: unit
   - metadata: metadata
   - meter_name: meter_name
   - direct: direct
   - samples: samples

Request Example
---------------

.. literalinclude:: ../samples/sample-create-request.json
   :language: javascript



Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - user_id: user_id
   - resource_id: resource_id
   - timestamp: timestamp
   - meter: meter
   - volume: volume
   - source: source
   - recorded_at: recorded_at
   - project_id: project_id
   - type: type
   - id: id
   - unit: unit
   - metadata: metadata



Response Example
----------------

.. literalinclude:: ../samples/sample-show-response.json
   :language: javascript




