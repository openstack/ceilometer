.. -*- rst -*-

======
Alarms
======

Lists, creates, gets details for, updates, and deletes alarms.


Show alarm details
==================

.. rest_method::  GET /v2/alarms/{alarm_id}

Shows details for an alarm, by alarm ID.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - alarm_actions: alarm_actions
   - alarm_id: alarm_id
   - combination_rule: combination_rule
   - description: description
   - enabled: enabled
   - insufficient_data_actions: insufficient_data_actions
   - timestamp: timestamp
   - name: name
   - ok_actions: ok_actions
   - project_id: project_id
   - state_timestamp: state_timestamp
   - threshold_rule: threshold_rule
   - repeat_actions: repeat_actions
   - state: state
   - type: type
   - user_id: user_id

Response Example
----------------

.. literalinclude:: ../samples/alarm-show-response.json
   :language: javascript




Update alarm
============

.. rest_method::  PUT /v2/alarms/{alarm_id}

Updates an alarm.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id
   - data: data


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - alarm_actions: alarm_actions
   - ok_actions: ok_actions
   - description: description
   - timestamp: timestamp
   - enabled: enabled
   - combination_rule: combination_rule
   - state_timestamp: state_timestamp
   - threshold_rule: threshold_rule
   - alarm_id: alarm_id
   - state: state
   - insufficient_data_actions: insufficient_data_actions
   - repeat_actions: repeat_actions
   - user_id: user_id
   - project_id: project_id
   - type: type
   - name: name



Response Example
----------------

.. literalinclude:: ../samples/alarm-show-response.json
   :language: javascript




Delete alarm
============

.. rest_method::  DELETE /v2/alarms/{alarm_id}

Deletes an alarm, by alarm ID.

Error response codes:204


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id






Update alarm state
==================

.. rest_method::  PUT /v2/alarms/{alarm_id}/state

Sets the state of an alarm.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id
   - state: state




Response Example
----------------

.. literalinclude::
   :language: javascript




Show alarm state
================

.. rest_method::  GET /v2/alarms/{alarm_id}/state

Shows the state for an alarm, by alarm ID.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id




Response Example
----------------

.. literalinclude::
   :language: javascript




List alarms
===========

.. rest_method::  GET /v2/alarms

Lists alarms, based on a query.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - q: q


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - alarm_actions: alarm_actions
   - ok_actions: ok_actions
   - description: description
   - timestamp: timestamp
   - enabled: enabled
   - combination_rule: combination_rule
   - state_timestamp: state_timestamp
   - threshold_rule: threshold_rule
   - alarm_id: alarm_id
   - state: state
   - insufficient_data_actions: insufficient_data_actions
   - repeat_actions: repeat_actions
   - user_id: user_id
   - project_id: project_id
   - type: type
   - name: name



Response Example
----------------

.. literalinclude:: ../samples/alarms-list-response.json
   :language: javascript




Create alarm
============

.. rest_method::  POST /v2/alarms

Creates an alarm.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - data: data


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - alarm_actions: alarm_actions
   - ok_actions: ok_actions
   - description: description
   - timestamp: timestamp
   - enabled: enabled
   - combination_rule: combination_rule
   - state_timestamp: state_timestamp
   - threshold_rule: threshold_rule
   - alarm_id: alarm_id
   - state: state
   - insufficient_data_actions: insufficient_data_actions
   - repeat_actions: repeat_actions
   - user_id: user_id
   - project_id: project_id
   - type: type
   - name: name



Response Example
----------------

.. literalinclude:: ../samples/alarm-show-response.json
   :language: javascript




Show alarm history
==================

.. rest_method::  GET /v2/alarms/{alarm_id}/history

Assembles and shows the history for an alarm, by alarm ID.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id
   - q: q




Response Example
----------------

.. literalinclude::
   :language: javascript
