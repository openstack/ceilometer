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

*  Tenant APIs: Tenant APIs are the ones that need to be polled in a tenant
   fashion. This feature is "a nice" to have, but is currently not
   implemented.


The dynamic pollsters system configuration (for OpenStack APIs)
---------------------------------------------------------------
Each YAML file in the dynamic pollster feature can use the following
attributes to define a dynamic pollster:

.. warning::
    Caution: Ceilometer does not accept complex value data structure for
    ``value`` and ``metadata`` configurations. Therefore, if you are extracting
    a complex data structure (Object, list, map, or others), you can take
    advantage of the ``Operations on extracted attributes`` feature to transform
    the object into a simple value (string or number)

*  ``name``: mandatory field. It specifies the name/key of the dynamic
   pollster. For instance, a pollster for magnum can use the name
   ``dynamic.magnum.cluster``;

*  ``sample_type``: mandatory field; it defines the sample type. It must
   be one of the values: ``gauge``, ``delta``, ``cumulative``;

*  ``unit``: mandatory field; defines the unit of the metric that is
   being collected. For magnum, for instance, one can use ``cluster`` as
   the unit or some other meaningful String value;

*  ``value_attribute``: mandatory attribute; defines the attribute in the
   response from the URL of the component being polled. We also accept
   nested values dictionaries. To use a nested value one can simply use
   ``attribute1.attribute2.<asMuchAsNeeded>.lastattribute``. It is also
   possible to reference the sample itself using ``"." (dot)``; the self
   reference of the sample is interesting in cases when the attribute might
   not exist. Therefore, together with the operations options, one can first
   check if it exist before retrieving it (example:
   ``". | value['some_field'] if 'some_field' in value else ''"``).
   In our magnum example, we can use ``status`` as the value attribute;

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
   retrieve. To use a nested value one can simply use
   ``attribute1.attribute2.<asMuchAsNeeded>.lastattribute``. As an example,
   for magnum, one can use the following values:

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

*  ``user_id_attribute``: optional parameter. The default value is ``user_id``.
   The name of the attribute in the entries that are processed from
   ``response_entries_key`` elements that will be mapped to ``user_id``
   attribute that is sent to Gnocchi.

*  ``project_id_attribute``: optional parameter. The default value is
   ``project_id``. The name of the attribute in the entries that are
   processed from ``response_entries_key`` elements that will be mapped to
   ``project_id`` attribute that is sent to Gnocchi.

*  ``resource_id_attribute``: optional parameter. The default value is ``id``.
   The name of the attribute in the entries that are processed from
   ``response_entries_key`` elements that will be mapped to ``id`` attribute
   that is sent to Gnocchi.

*  ``headers``: optional parameter. It is a map (similar to the
   metadata_mapping) of key and value that can be used to customize the header
   of the request that is executed against the URL. This configuration works
   for both OpenStack and non-OpenStack dynamic pollster configuration.

  .. code-block:: yaml

    headers:
      "x-openstack-nova-api-version": "2.46"

*  ``timeout``: optional parameter. Defines the request timeout for the
   requests executed by the dynamic pollsters to gather data. The default
   timeout value is 30 seconds. If it is set to `None`, this means that the
   request never times out on the client side. Therefore, one might have
   problems if the server never closes the connection. The pollsters are
   executed serially, one after the other. Therefore, if the request hangs,
   all pollsters (including the non-dynamic ones) will stop executing.

*  ``namespaces``: optional parameter. Defines the namespaces (running
   ceilometer instances) where the pollster will be instantiated. This
   parameter accepts a single string value or a list of strings. The
   default value is `central`.

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

*  ``response_handlers``: optional parameter. Defines the response
   handlers used to handle the response. For now, the supported values
   are:

   ``json``: This handler will interpret the response as a `JSON` and will
   convert it to a `dictionary` which can be manipulated using the
   operations options when mapping the attributes:

   .. code-block:: yaml

     ---

     - name: "dynamic.json.response"
       sample_type: "gauge"
       [...]
       response_handlers:
          - json

   Response to handle:

   .. code-block:: json

     {
        "test": {
          "list": [1, 2, 3]
        }
     }

   Response handled:

   .. code-block:: python

     {
        'test': {
          'list': [1, 2, 3]
        }
     }


   ``xml``: This handler will interpret the response as an `XML` and will
   convert it to a `dictionary` which can be manipulated using the
   operations options when mapping the attributes:

   .. code-block:: yaml

     ---

     - name: "dynamic.json.response"
       sample_type: "gauge"
       [...]
       response_handlers:
          - xml

   Response to handle:

   .. code-block:: xml

     <test>
       <list>1</list>
       <list>2</list>
       <list>3</list>
     </test>

   Response handled:

   .. code-block:: python

     {
        'test': {
          'list': [1, 2, 3]
        }
     }

   ``text``: This handler will interpret the response as a `PlainText` and
   will convert it to a `dictionary` which can be manipulated using the
   operations options when mapping the attributes:

   .. code-block:: yaml

     ---

     - name: "dynamic.json.response"
       sample_type: "gauge"
       [...]
       response_handlers:
          - text

   Response to handle:

   .. code-block:: text

     Plain text response

   Response handled:

   .. code-block:: python

     {
        'out': "Plain text response"
     }

   They can be used together or individually. If not defined, the
   `default` value will be `json`. If you set 2 or more response
   handlers, the first configured handler will be used to try to
   handle the response, if it is not possible, a `DEBUG` log
   message will be displayed, then the next will be used
   and so on. If no configured handler was able to handle
   the response, an empty dict will be returned and a `WARNING`
   log will be displayed to warn operators that the response was
   not able to be handled by any configured handler.

The dynamic pollsters system configuration (for non-OpenStack APIs)
-------------------------------------------------------------------

The dynamic pollster system can also be used for non-OpenStack APIs.
to configure non-OpenStack APIs, one can use all but one attribute of
the Dynamic pollster system. The attribute that is not supported is
the ``endpoint_type``. The dynamic pollster system for non-OpenStack APIs
is activated automatically when one uses the configurations ``module``.

The extra parameters (in addition to the original ones) that are available
when using the Non-OpenStack dynamic pollster sub-subsystem are the following:

*  ``module``: required parameter. It is the python module name that Ceilometer
   has to load to use the authentication object when executing requests against
   the API. For instance, if one wants to create a pollster to gather data from
   RadosGW, he/she can use the ``awsauth`` python module.

* ``authentication_object``: mandatory parameter. The name of the class that we
  can find in the ``module`` that Ceilometer will use as the authentication
  object in the request. For instance, when using the ``awsauth`` python module
  to gather data from RadosGW, one can use the authentication object as
  ``S3Auth``.

* ``authentication_parameters``: optional parameter. It is a comma separated
  value that will be used to instantiate the ``authentication_object``. For
  instance, if we gather data from RadosGW, and we use the ``S3Auth`` class,
  the ``authentication_parameters`` can be configured as
  ``<rados_gw_access_key>, rados_gw_secret_key, rados_gw_host_name``.

* ``barbican_secret_id``: optional parameter. The Barbican secret ID,
  from which, Ceilometer can retrieve the comma separated values of the
  ``authentication_parameters``.

As follows we present an example on how to convert the hard-coded pollster
for `radosgw.api.request` metric to the dynamic pollster model:

.. code-block:: yaml

  ---

  - name: "dynamic.radosgw.api.request"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "total.ops"
    url_path: "http://rgw.service.stage.i.ewcs.ch/admin/usage"
    module: "awsauth"
    authentication_object: "S3Auth"
    authentication_parameters: "<access_key>,<secret_key>,<rados_gateway_server>"
    user_id_attribute: "user"
    project_id_attribute: "user"
    resource_id_attribute: "user"
    response_entries_key: "summary"

We can take that example a bit further, and instead of gathering the `total
.ops` variable, which counts for all the requests (even the unsuccessful
ones), we can use the `successful_ops`.

.. code-block:: yaml

  ---

  - name: "dynamic.radosgw.api.request.successful_ops"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "total.successful_ops"
    url_path: "http://rgw.service.stage.i.ewcs.ch/admin/usage"
    module: "awsauth"
    authentication_object: "S3Auth"
    authentication_parameters: "<access_key>, <secret_key>,<rados_gateway_server>"
    user_id_attribute: "user"
    project_id_attribute: "user"
    resource_id_attribute: "user"
    response_entries_key: "summary"

The dynamic pollsters system configuration (for local host commands)
--------------------------------------------------------------------

The dynamic pollster system can also be used for local host commands,
these commands must be installed in the system that is running the
Ceilometer compute agent.
To configure local hosts commands, one can use all but two attributes of
the Dynamic pollster system. The attributes that are not supported are
the ``endpoint_type`` and ``url_path``. The dynamic pollster system for
local host commands is activated automatically when one uses the
configuration ``host_command``.

The extra parameter (in addition to the original ones) that is available
when using the local host commands dynamic pollster sub-subsystem is the
following:

*  ``host_command``: required parameter. It is the host command that will
   be executed in the same host the Ceilometer dynamic pollster agent is
   running. The output of the command will be processed by the pollster and
   stored in the configured backend.

As follows we present an example on how to use the local host command:

.. code-block:: yaml

  ---

  - name: "dynamic.host.command"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "value"
    response_entries_key: "test"
    host_command: "echo '<test><user_id>id1_u</user_id><project_id>id1_p</project_id><id>id1</id><meta>meta-data-to-store</meta><value>1</value></test>'"
    metadata_fields:
        - "meta"
    response_handlers:
        - xml

To execute multi page host commands, the `next_sample_url_attribute`
must generate the next sample command, like the following example:

.. code-block:: yaml

  ---

  - name: "dynamic.s3.objects.size"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "Size"
    project_id_attribute: "Owner.ID"
    user_id_attribute: "Owner.ID"
    resource_id_attribute: "Key"
    response_entries_key: "Contents"
    host_command: "aws s3api list-objects"
    next_sample_url_attribute: NextToken | 'aws s3api list-objects --starting-token "' + value + '"'

Operations on extracted attributes
----------------------------------

The dynamic pollster system can execute Python operations to transform the
attributes that are extracted from the JSON response that the system handles.

One example of use case is the RadosGW that uses <project_id$project_id> as the
username (which is normally mapped to the Gnocchi resource_id). With this
feature (operations on extracted attributes), one can create configurations in
the dynamic pollster to clean/normalize that variable. It is as simple as
defining `resource_id_attribute: "user | value.split('$')[0].strip()"`

The operations are separated by `|` symbol. The first element of the expression
is the key to be retrieved from the JSON object. The other elements are
operations that can be applied to the `value` variable. The value variable
is the variable we use to hold the data being extracted. The previous
example can be rewritten as:
`resource_id_attribute: "user | value.split ('$') | value[0] | value.strip()"`

As follows we present a complete configuration for a RadosGW dynamic
pollster that is removing the `$` symbol, and getting the first part of the
String.

.. code-block:: yaml

  ---

  - name: "dynamic.radosgw.api.request.successful_ops"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "total.successful_ops"
    url_path: "http://rgw.service.stage.i.ewcs.ch/admin/usage"
    module: "awsauth"
    authentication_object: "S3Auth"
    authentication_parameters: "<access_key>,<secret_key>,<rados_gateway_server>"
    user_id_attribute: "user | value.split ('$') | value[0]"
    project_id_attribute: "user | value.split ('$') | value[0]"
    resource_id_attribute: "user | value.split ('$') | value[0]"
    response_entries_key: "summary"

The Dynamic pollster configuration options that support this feature are the
following:

* value_attribute
* response_entries_key
* user_id_attribute
* project_id_attribute
* resource_id_attribute

Multi metric dynamic pollsters (handling attribute values with list of objects)
-------------------------------------------------------------------------------

The initial idea for this feature comes from the `categories` fields that we
can find in the `summary` object of the RadosGW API. Each user has a
`categories` attribute in the response; in the `categories` list, we can find
the object that presents in a granular fashion the consumption of different
RadosGW API operations such as GET, PUT, POST, and may others.

As follows we present an example of such a JSON response.

.. code-block:: json

  {
      "entries": [
          {
              "buckets": [
                  {
                      "bucket": "",
                      "categories": [
                          {
                              "bytes_received": 0,
                              "bytes_sent": 40,
                              "category": "list_buckets",
                              "ops": 2,
                              "successful_ops": 2
                          }
                      ],
                      "epoch": 1572969600,
                      "owner": "user",
                      "time": "2019-11-21 00:00:00.000000Z"
                  },
                  {
                      "bucket": "-",
                      "categories": [
                          {
                              "bytes_received": 0,
                              "bytes_sent": 0,
                              "category": "get_obj",
                              "ops": 1,
                              "successful_ops": 0
                          }
                      ],
                      "epoch": 1572969600,
                      "owner": "someOtherUser",
                      "time": "2019-11-21 00:00:00.000000Z"
                  }
              ]
          }
      ]
      "summary": [
          {
              "categories": [
                  {
                      "bytes_received": 0,
                      "bytes_sent": 0,
                      "category": "create_bucket",
                      "ops": 2,
                      "successful_ops": 2
                  },
                  {
                      "bytes_received": 0,
                      "bytes_sent": 2120428,
                      "category": "get_obj",
                      "ops": 46,
                      "successful_ops": 46
                  },
                  {
                      "bytes_received": 0,
                      "bytes_sent": 21484,
                      "category": "list_bucket",
                      "ops": 8,
                      "successful_ops": 8
                  },
                  {
                      "bytes_received": 6889056,
                      "bytes_sent": 0,
                      "category": "put_obj",
                      "ops": 46,
                      "successful_ops": 46
                  }
              ],
              "total": {
                  "bytes_received": 6889056,
                  "bytes_sent": 2141912,
                  "ops": 102,
                  "successful_ops": 102
              },
              "user": "user"
          },
          {
              "categories": [
                  {
                      "bytes_received": 0,
                      "bytes_sent": 0,
                      "category": "create_bucket",
                      "ops": 1,
                      "successful_ops": 1
                  },
                  {
                      "bytes_received": 0,
                      "bytes_sent": 0,
                      "category": "delete_obj",
                      "ops": 23,
                      "successful_ops": 23
                  },
                  {
                      "bytes_received": 0,
                      "bytes_sent": 5371,
                      "category": "list_bucket",
                      "ops": 2,
                      "successful_ops": 2
                  },
                  {
                      "bytes_received": 3444350,
                      "bytes_sent": 0,
                      "category": "put_obj",
                      "ops": 23,
                      "successful_ops": 23
                  }
              ],
              "total": {
                  "bytes_received": 3444350,
                  "bytes_sent": 5371,
                  "ops": 49,
                  "successful_ops": 49
              },
              "user": "someOtherUser"
          }
      ]
  }

In that context, and having in mind that we have APIs with similar data
structures, we developed an extension for the dynamic pollster that enables
multi-metric processing for a single pollster. It works as follows.

The pollster name will contain a placeholder for the variable that
identifies the "submetric". E.g. `dynamic.radosgw.api.request.{category}`.
The placeholder `{category}` indicates the object's attribute that is in the
list of objects that we use to load the sub metric name. Then, we must use a
special notation in the `value_attribute` configuration to indicate that we are
dealing with a list of objects. This is achieved via `[]` (brackets); for
instance, in the `dynamic.radosgw.api.request.{category}`, we can use
`[categories].ops` as the `value_attribute`. This indicates that the value we
retrieve is a list of objects, and when the dynamic pollster processes it, we
want it (the pollster) to load the `ops` value for the sub metrics being
generated.

Examples on how to create multi-metric pollster to handle data from RadosGW API
are presented as follows:

.. code-block:: yaml

  ---

  - name: "dynamic.radosgw.api.request.{category}"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "[categories].ops"
    url_path: "http://rgw.service.stage.i.ewcs.ch/admin/usage"
    module: "awsauth"
    authentication_object: "S3Auth"
    authentication_parameters:  "<access_key>, <secret_key>,<rados_gateway_server>"
    user_id_attribute: "user | value.split('$')[0]"
    project_id_attribute: "user | value.split('$') | value[0]"
    resource_id_attribute: "user  | value.split('$') | value[0]"
    response_entries_key: "summary"

  - name: "dynamic.radosgw.api.request.successful_ops.{category}"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "[categories].successful_ops"
    url_path: "http://rgw.service.stage.i.ewcs.ch/admin/usage"
    module: "awsauth"
    authentication_object: "S3Auth"
    authentication_parameters:  "<access_key>, <secret_key>,<rados_gateway_server>"
    user_id_attribute: "user | value.split('$')[0]"
    project_id_attribute: "user | value.split('$') | value[0]"
    resource_id_attribute: "user  | value.split('$') | value[0]"
    response_entries_key: "summary"

  - name: "dynamic.radosgw.api.bytes_sent.{category}"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "[categories].bytes_sent"
    url_path: "http://rgw.service.stage.i.ewcs.ch/admin/usage"
    module: "awsauth"
    authentication_object: "S3Auth"
    authentication_parameters:  "<access_key>, <secret_key>,<rados_gateway_server>"
    user_id_attribute: "user | value.split('$')[0]"
    project_id_attribute: "user | value.split('$') | value[0]"
    resource_id_attribute: "user  | value.split('$') | value[0]"
    response_entries_key: "summary"

  - name: "dynamic.radosgw.api.bytes_received.{category}"
    sample_type: "gauge"
    unit: "request"
    value_attribute: "[categories].bytes_received"
    url_path: "http://rgw.service.stage.i.ewcs.ch/admin/usage"
    module: "awsauth"
    authentication_object: "S3Auth"
    authentication_parameters:  "<access_key>, <secret_key>,<rados_gateway_server>"
    user_id_attribute: "user | value.split('$')[0]"
    project_id_attribute: "user | value.split('$') | value[0]"
    resource_id_attribute: "user  | value.split('$') | value[0]"
    response_entries_key: "summary"

Handling linked API responses
-----------------------------
If the consumed API returns a linked response which contains a link to the next
response set (page), the Dynamic pollsters can be configured to follow these
links and join all linked responses into a single one.

To enable this behavior the operator will need to configure the parameter
`next_sample_url_attribute` that must contain a mapper to the response
attribute that contains the link to the next response page. This parameter also
supports operations like the others `*_attribute` dynamic pollster's
parameters.

Examples on how to create a pollster to handle linked API responses are
presented as follows:

- Example of a simple linked response:

    - API response:

    .. code-block:: json

        {
          "server_link": "http://test.com/v1/test-volumes/marker=c3",
          "servers": [
            {
              "volume": [
                {
                  "name": "a",
                  "tmp": "ra"
                }
              ],
              "id": 1,
              "name": "a1"
            },
            {
              "volume": [
                {
                  "name": "b",
                  "tmp": "rb"
                }
              ],
              "id": 2,
              "name": "b2"
            },
            {
              "volume": [
                {
                  "name": "c",
                  "tmp": "rc"
                }
              ],
              "id": 3,
              "name": "c3"
            }
          ]
        }

    - Pollster configuration:

    .. code-block:: yaml

      ---

      - name: "dynamic.linked.response"
        sample_type: "gauge"
        unit: "request"
        value_attribute: "[volume].tmp"
        url_path: "v1/test-volumes"
        response_entries_key: "servers"
        next_sample_url_attribute: "server_link"

- Example of a complex linked response:

    - API response:

    .. code-block:: json

        {
          "server_link": [
            {
              "href": "http://test.com/v1/test-volumes/marker=c3",
              "rel": "next"
            },
            {
              "href": "http://test.com/v1/test-volumes/marker=b1",
              "rel": "prev"
            }
          ],
          "servers": [
            {
              "volume": [
                {
                  "name": "a",
                  "tmp": "ra"
                }
              ],
              "id": 1,
              "name": "a1"
            },
            {
              "volume": [
                {
                  "name": "b",
                  "tmp": "rb"
                }
              ],
              "id": 2,
              "name": "b2"
            },
            {
              "volume": [
                {
                  "name": "c",
                  "tmp": "rc"
                }
              ],
              "id": 3,
              "name": "c3"
            }
          ]
        }

    - Pollster configuration:

    .. code-block:: yaml

      ---

      - name: "dynamic.linked.response"
        sample_type: "gauge"
        unit: "request"
        value_attribute: "[volume].tmp"
        url_path: "v1/test-volumes"
        response_entries_key: "servers"
        next_sample_url_attribute: "server_link | filter(lambda v: v.get('rel') == 'next', value) | list(value) | value[0] | value.get('href')"

OpenStack Dynamic pollsters metadata enrichment with other OpenStack API's data
-------------------------------------------------------------------------------

Sometimes we want/need to add/gather extra metadata for the samples being
handled by Ceilometer Dynamic pollsters, such as the project name, domain id,
domain name, and other metadata that are not always accessible via the
OpenStack component where the sample is gathered.

For instance, when gathering the status of virtual machines (VMs) from Nova,
we only have the `tenant_id`, which must be used as the `project_id`. However,
for billing and later invoicing one might need/want the project name, domain
id, and other metadata that are available in Keystone (and maybe some others
that are scattered over other components). To achieve that, one can use the
OpenStack metadata enrichment option. As follows we present an example that
shows a dynamic pollster configuration to gather virtual machine (VM) status,
and to enrich the data pushed to the storage backend (e.g. Gnocchi) with
project name, domain ID, and domain name.

    .. code-block:: yaml

      ---

      - name: "dynamic_pollster.instance.status"
        next_sample_url_attribute: "server_links | filter(lambda v: v.get('rel') == 'next', value) | list(value) | value[0] | value.get('href') | value.replace('http:', 'https:')"
        sample_type: "gauge"
        unit: "server"
        value_attribute: "status"
        endpoint_type: "compute"
        url_path: "/v2.1/servers/detail?all_tenants=true"
        headers:
          "Openstack-API-Version": "compute 2.65"
        project_id_attribute: "tenant_id"
        metadata_fields:
          - "status"
          - "name"
          - "flavor.vcpus"
          - "flavor.ram"
          - "flavor.disk"
          - "flavor.ephemeral"
          - "flavor.swap"
          - "flavor.original_name"
          - "image | value or { 'id': '' } | value['id']"
          - "OS-EXT-AZ:availability_zone"
          - "OS-EXT-SRV-ATTR:host"
          - "user_id"
          - "tags | ','.join(value)"
          - "locked"
        value_mapping:
          ACTIVE: "1"
        default_value: 0
        metadata_mapping:
          "OS-EXT-AZ:availability_zone": "dynamic_availability_zone"
          "OS-EXT-SRV-ATTR:host": "dynamic_host"
          "flavor.original_name": "dynamic_flavor_name"
          "flavor.vcpus": "dynamic_flavor_vcpus"
          "flavor.ram": "dynamic_flavor_ram"
          "flavor.disk": "dynamic_flavor_disk"
          "flavor.ephemeral": "dynamic_flavor_ephemeral"
          "flavor.swap": "dynamic_flavor_swap"
          "image | value or { 'id': '' } | value['id']": "dynamic_image_ref"
          "name": "dynamic_display_name"
          "locked": "dynamic_locked"
          "tags | ','.join(value)": "dynamic_tags"
        extra_metadata_fields_cache_seconds: 3600
        extra_metadata_fields_skip:
          - value: '1'
            metadata:
              dynamic_flavor_vcpus: 4
          - value: '1'
            metadata:
              dynamic_flavor_vcpus: 2
        extra_metadata_fields:
          - name: "project_name"
            endpoint_type: "identity"
            url_path: "'/v3/projects/' + str(sample['project_id'])"
            headers:
              "Openstack-API-Version": "identity latest"
            value: "name"
            extra_metadata_fields_cache_seconds: 1800 # overriding the default cache policy
            metadata_fields:
                - id
          - name: "domain_id"
            endpoint_type: "identity"
            url_path: "'/v3/projects/' + str(sample['project_id'])"
            headers:
              "Openstack-API-Version": "identity latest"
            value: "domain_id"
            metadata_fields:
                - id
          - name: "domain_name"
            endpoint_type: "identity"
            url_path: "'/v3/domains/' + str(extra_metadata_captured['domain_id'])"
            headers:
              "Openstack-API-Version": "identity latest"
            value: "name"
            metadata_fields:
                - id
          - name: "operating-system"
            host_command: "'get-vm --vm-name ' + str(extra_metadata_by_name['project_name']['metadata']['id'])"
            value: "os"


The above example can be used to gather and persist in the backend the
status of VMs. It will persist `1` in the backend as a measure for every
collecting period if the VM's status is `ACTIVE`, and `0` otherwise. This is
quite useful to create hashmap rating rules for running VMs in CloudKitty.
Then, to enrich the resource in the storage backend, we are adding extra
metadata that are collected in Keystone and in the local host via the
`extra_metadata_fields` options. If you have multiples `extra_metadata_fields`
defining the same `metadata_field`, the last not `None` metadata value will
be used.

To operate values in the `extra_metadata_fields`, you can access 3 local
variables:

*  ``sample``: it is a dictionary which holds the current data of the root
   sample. The root sample is the final sample that will be persisted in the
   configured storage backend.

*  ``extra_metadata_captured``: it is a dictionary which holds the current
   data of all `extra_metadata_fields` processed before this one.
   If you have multiples `extra_metadata_fields` defining the same
   `metadata_field`, the last not `None` metadata value will be used.

*  ``extra_metadata_by_name``: it is a dictionary which holds the data of
   all `extra_metadata_fields` processed before this one. No data is
   overwritten in this variable. To access an specific `extra_metadata_field`
   using this variable, you can do
   `extra_metadata_by_name['<extra_metadata_field_name>']['value']` to get
   its value, or
   `extra_metadata_by_name['<extra_metadata_field_name>']['metadata']['<metadata>']`
   to get its metadata.

The metadata enrichment feature has the following options:

*  ``extra_metadata_fields_cache_seconds``: optional parameter. Defines the
   extra metadata request's response cache. Some requests, such as the ones
   executed against Keystone to retrieve extra metadata are rather static.
   Therefore, one does not need to constantly re-execute the request. That
   is the reason why we cache the response of such requests. By default the
   cache time to live (TTL) for responses is `3600` seconds. However, this
   value can be increased of decreased.

*  ``extra_metadata_fields``: optional parameter. This option is a list of
   objects or a single one, where each one of its elements is an
   dynamic pollster configuration set. Each one of the extra metadata
   definition can have the same options defined in the dynamic pollsters,
   including the `extra_metadata_fields` option, so this option is a
   multi-level option. When defined, the result of the collected data will
   be merged in the final sample resource metadata. If some of the required
   dynamic pollster configuration is not set in the `extra_metadata_fields`,
   will be used the parent pollster configuration, except the `name`.

*  ``extra_metadata_fields_skip``: optional parameter. This option is a list
   of objects or a single one, where each one of its elements is a set of
   key/value pairs. When defined, if any set of key/value pairs is a subset
   of the collected sample, then the extra_metadata_fields gathering of this
   sample will be skipped.


