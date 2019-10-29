.. _telemetry_dynamic_pollster:

Introduction to dynamic pollster subsystem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The dynamic pollster feature allows system administrators to
create/update REST API pollsters on the fly (without changing code).
The system reads YAML configures that are found in
``pollsters_definitions_dirs`` parameter, which has the default at
``/etc/ceilometer/pollsters.d``. Operators can use a single file per
dynamic pollster or multiple dynamic pollsters per file.


Current limitations of the dynamic pollster system
--------------------------------------------------
Currently, the following types of APIs are not supported by the
dynamic pollster system:

*  Paging APIs: if a user configures a dynamic pollster to gather data
   from a paging API, the pollster will use only the entries from the first
   page.

*  Tenant APIs: Tenant APIs are the ones that need to be polled in a tenant
   fashion. This feature is "a nice" to have, but is currently not
   implemented.

*  non-OpenStack APIs such as RadosGW (currently in development)

*  APIs that return a list of entries directly, without a first key for the
   list. An example is Aodh alarm list.


The dynamic pollsters system configuration
------------------------------------------
Each YAML file in the dynamic pollster feature can use the following
attributes to define a dynamic pollster:

*  ``name``: mandatory field. It specifies the name/key of the dynamic
   pollster. For instance, a pollster for magnum can use the name
   ``dynamic.magnum.cluster``;

*  ``sample_type``: mandatory field; it defines the sample type. It must
   be one of the values: ``gauge``, ``delta``, ``cumulative``;

*  ``unit``: mandatory field; defines the unit of the metric that is
   being collected. For magnum, for instance, one can use ``cluster`` as
   the unit or some other meaningful String value;

*  ``value_attribute``: mandatory attribute; defines the attribute in the
   JSON response from the URL of the component being polled. We also accept
   nested values dictionaries. To use a nested value one can simply use
   ``attribute1.attribute2.<asMuchAsNeeded>.lastattribute``. In our magnum
   example, we can use ``status`` as the value attribute;

*  ``endpoint_type``: mandatory field; defines the endpoint type that is
   used to discover the base URL of the component to be monitored; for
   magnum, one can use ``container-infra``. Other values are accepted such
   as ``volume`` for cinder endpoints, ``object-store`` for swift, and so
   on;

*  ``url_path``: mandatory attribute. It defines the path of the request
   that we execute on the endpoint to gather data. For example, to gather
   data from magnum, one can use ``v1/clusters/detail``;

*  ``metadata_fields``: optional field. It is a list of all fields that
   the response of the request executed with ``url_path`` that we want to
   retrieve. As an example, for magnum, one can use the following values:

  .. code-block:: yaml

    metadata_fields:
      - "labels"
      - "updated_at"
      - "keypair"
      - "master_flavor_id"
      - "api_address"
      - "master_addresses"
      - "node_count"
      - "docker_volume_size"
      - "master_count"
      - "node_addresses"
      - "status_reason"
      - "coe_version"
      - "cluster_template_id"
      - "name"
      - "stack_id"
      - "created_at"
      - "discovery_url"
      - "container_version"

*  ``skip_sample_values``: optional field. It defines the values that
   might come in the ``value_attribute`` that we want to ignore. For
   magnun, one could for instance, ignore some of the status it has for
   clusters. Therefore, data is not gathered for clusters in the defined
   status.

  .. code-block:: yaml

    skip_sample_values:
      - "CREATE_FAILED"
      - "DELETE_FAILED"

*  ``value_mapping``: optional attribute. It defines a mapping for the
   values that the dynamic pollster is handling. This is the actual value
   that is sent to Gnocchi or other backends. If there is no mapping
   specified, we will use the raw value that is obtained with the use of
   ``value_attribute``. An example for magnum, one can use:

  .. code-block:: yaml

    value_mapping:
      CREATE_IN_PROGRESS: "0"
      CREATE_FAILED: "1"
      CREATE_COMPLETE: "2"
      UPDATE_IN_PROGRESS: "3"
      UPDATE_FAILED: "4"
      UPDATE_COMPLETE: "5"
      DELETE_IN_PROGRESS: "6"
      DELETE_FAILED: "7"
      DELETE_COMPLETE: "8"
      RESUME_COMPLETE: "9"
      RESUME_FAILED: "10"
      RESTORE_COMPLETE: "11"
      ROLLBACK_IN_PROGRESS: "12"
      ROLLBACK_FAILED: "13"
      ROLLBACK_COMPLETE: "14"
      SNAPSHOT_COMPLETE: "15"
      CHECK_COMPLETE: "16"
      ADOPT_COMPLETE: "17"

*  ``default_value``: optional parameter. The default value for
   the value mapping in case the variable value receives data that is not
   mapped to something in the ``value_mapping`` configuration. This
   attribute is only used when ``value_mapping`` is defined. Moreover, it
   has a default of ``-1``.

*  ``metadata_mapping``: optional parameter. The map used to create new
   metadata fields. The key is a metadata name that exists in the response
   of the request we make, and the value of this map is the new desired
   metadata field that will be created with the content of the metadata that
   we are mapping. The ``metadata_mapping`` can be created as follows:

  .. code-block:: yaml

    metadata_mapping:
      name: "display_name"
      some_attribute: "new_attribute_name"

*  ``preserve_mapped_metadata``: optional parameter. It indicates if we
   preserve the old metadata name when it gets mapped to a new one.
   The default value is ``True``.

*  ``response_entries_key``: optional parameter. This value is used to define
   the "key" of the response that will be used to look-up the entries used in
   the dynamic pollster processing. If no ``response_entries_key`` is informed
   by the operator, we will use the first we find. Moreover, if the response
   contains a list, instead of an object where one of its attributes is a list
   of entries, we use the list directly. Therefore, this option will be
   ignored when the API is returning the list/array of entries to be processed
   directly. We also accept nested values dictionaries. To use a nested value
   one can simply use ``attribute1.attribute2.<asMuchAsNeeded>.lastattribute``


The complete YAML configuration to gather data from Magnum (that has been used
as an example) is the following:

.. code-block:: yaml

  ---

  - name: "dynamic.magnum.cluster"
    sample_type: "gauge"
    unit: "cluster"
    value_attribute: "status"
    endpoint_type: "container-infra"
    url_path: "v1/clusters/detail"
    metadata_fields:
      - "labels"
      - "updated_at"
      - "keypair"
      - "master_flavor_id"
      - "api_address"
      - "master_addresses"
      - "node_count"
      - "docker_volume_size"
      - "master_count"
      - "node_addresses"
      - "status_reason"
      - "coe_version"
      - "cluster_template_id"
      - "name"
      - "stack_id"
      - "created_at"
      - "discovery_url"
      - "container_version"
    value_mapping:
      CREATE_IN_PROGRESS: "0"
      CREATE_FAILED: "1"
      CREATE_COMPLETE: "2"
      UPDATE_IN_PROGRESS: "3"
      UPDATE_FAILED: "4"
      UPDATE_COMPLETE: "5"
      DELETE_IN_PROGRESS: "6"
      DELETE_FAILED: "7"
      DELETE_COMPLETE: "8"
      RESUME_COMPLETE: "9"
      RESUME_FAILED: "10"
      RESTORE_COMPLETE: "11"
      ROLLBACK_IN_PROGRESS: "12"
      ROLLBACK_FAILED: "13"
      ROLLBACK_COMPLETE: "14"
      SNAPSHOT_COMPLETE: "15"
      CHECK_COMPLETE: "16"
      ADOPT_COMPLETE: "17"

We can also replicate and enhance some hardcoded pollsters.
For instance, the pollster to gather VPN connections. Currently,
it is always persisting `1` for all of the VPN connections it finds.
However, the VPN connection can have multiple statuses, and we should
normally only bill for active resources, and not resources on `ERROR`
states. An example to gather VPN connections data is the following
(this is just an example, and one can adapt and configure as he/she
desires):

.. code-block:: yaml

  ---

  - name: "dynamic.network.services.vpn.connection"
  sample_type: "gauge"
  unit: "ipsec_site_connection"
  value_attribute: "status"
  endpoint_type: "network"
  url_path: "v2.0/vpn/ipsec-site-connections"
  metadata_fields:
    - "name"
    - "vpnservice_id"
    - "description"
    - "status"
    - "peer_address"
  value_mapping:
    ACTIVE: "1"
  metadata_mapping:
    name: "display_name"
  default_value: 0
