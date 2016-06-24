.. -*- rst -*-

=======
Samples
=======

Lists all samples and gets information for a sample.

For list operations, if you do not explicitly set the ``limit``
query parameter, a default limit is applied. The default limit is
the ``default_api_return_limit`` configuration option value.


Show sample details
===================

.. rest_method::  GET /v2/samples/{sample_id}

Shows details for a sample, by sample ID.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - sample_id: sample_id


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




List samples
============

.. rest_method::  GET /v2/samples

Lists all known samples, based on the data recorded so far.


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



