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

   - alarm_id: alarm_id_path


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - alarm: alarm_response
   - alarm_actions: alarm_actions
   - alarm_id: alarm_id
   - combination_rule: alarm_combination_rule
   - description: alarm_description
   - enabled: alarm_enabled
   - insufficient_data_actions: alarm_insufficient_data_actions
   - timestamp: alarm_timestamp
   - name: alarm_name
   - ok_actions: alarm_ok_actions
   - project_id: alarm_project_id
   - state_timestamp: alarm_state_timestamp
   - threshold_rule: alarm_threshold_rule
   - repeat_actions: alarm_repeat_actions
   - state: alarm_state
   - type: alarm_type
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

   - alarm_id: alarm_id_path
   - alarm: alarm_request


Response Parameters
-------------------

.. rest_parameters:: parameters.yaml

   - alarm: alarm_response
   - alarm_actions: alarm_actions
   - alarm_id: alarm_id
   - combination_rule: alarm_combination_rule
   - description: alarm_description
   - enabled: alarm_enabled
   - insufficient_data_actions: alarm_insufficient_data_actions
   - timestamp: alarm_timestamp
   - name: alarm_name
   - ok_actions: alarm_ok_actions
   - project_id: alarm_project_id
   - state_timestamp: alarm_state_timestamp
   - threshold_rule: alarm_threshold_rule
   - repeat_actions: alarm_repeat_actions
   - state: alarm_state
   - type: alarm_type
   - user_id: user_id



Response Example
----------------

.. literalinclude:: ../samples/alarm-show-response.json
   :language: javascript




Delete alarm
============

.. rest_method::  DELETE /v2/alarms/{alarm_id}

Deletes an alarm, by alarm ID.

Normal response codes:204


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id_path






Update alarm state
==================

.. rest_method::  PUT /v2/alarms/{alarm_id}/state

Sets the state of an alarm.


Normal response codes: 200
Error response codes:


Request
-------

.. rest_parameters:: parameters.yaml

   - alarm_id: alarm_id_path
   - state: alarm_state




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

   - alarm_id: alarm_id_path




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
   - insufficient_data_actions: alarm_insufficient_data_actions
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

   - alarm: alarm_response
   - alarm_actions: alarm_actions
   - alarm_id: alarm_id
   - combination_rule: alarm_combination_rule
   - description: alarm_description
   - enabled: alarm_enabled
   - insufficient_data_actions: alarm_insufficient_data_actions
   - timestamp: alarm_timestamp
   - name: alarm_name
   - ok_actions: alarm_ok_actions
   - project_id: alarm_project_id
   - state_timestamp: alarm_state_timestamp
   - threshold_rule: alarm_threshold_rule
   - repeat_actions: alarm_repeat_actions
   - state: alarm_state
   - type: alarm_type
   - user_id: user_id



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

   - alarm_id: alarm_id_path
   - q: q




Response Example
----------------

.. literalinclude::
   :language: javascript
