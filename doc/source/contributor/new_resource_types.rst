..
      Copyright 2017 EasyStack, Inc.

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

.. _add_new_resource_types:

================================
Ceilometer + Gnocchi Integration
================================

.. warning::

    Remember that custom modification may result in conflicts with upstream upgrades.
    If not intended to be merged with upstream, it's advisable to directly create
    resource-types via Gnocchi API.

.. _resource_types:

Managing Resource Types
=======================

Resource types in Gnocchi are managed by Ceilometer. The following describes
how to add/remove or update Gnocchi resource types to support new Ceilometer
data.

The modification or creation of Gnocchi resource type definitions are managed
`resources_update_operations` of :file:`ceilometer/gnocchi_client.py`.

The following operations are supported:

1. Adding a new attribute to a resource type. The following adds `flavor_name`
   attribute to an existing `instance` resource:

.. code::

    {"desc": "add flavor_name to instance",
     "type": "update_attribute_type",
     "resource_type": "instance",
     "data": [{
         "op": "add",
         "path": "/attributes/flavor_name",
         "value": {"type": "string", "min_length": 0, "max_length": 255,
                   "required": True, "options": {'fill': ''}}
     }]}

2. Remove an existing attribute from a resource type. The following removes
   `server_group` attribute from `instance` resource:

.. code::

    {"desc": "remove server_group to instance",
     "type": "update_attribute_type",
     "resource_type": "instance",
     "data": [{
         "op": "remove",
         "path": "/attributes/server_group"
     }]}

3. Creating a new resource type. The following creates a new resource type
   named `nova_compute` with a required attribute `host_name`:

.. code::

    {"desc": "add nova_compute resource type",
     "type": "create_resource_type",
     "resource_type": "nova_compute",
     "data": [{
         "attributes": {"host_name": {"type": "string", "min_length": 0,
                        "max_length": 255, "required": True}}
     }]}

.. note::

    Do not modify the existing change steps when making changes.
    Each modification requires a new step to be added and for
    `ceilometer-upgrade` to be run to apply the change to Gnocchi.

With accomplishing sections above, don't forget to add a new resource type or
attributes of a resource type into
the :file:`ceilometer/publisher/data/gnocchi_resources.yaml`.
