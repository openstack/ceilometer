..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode


.. _paas_event_format:

=================
PaaS Event Format
=================

There are a number of PaaS services that are currently under development
and a growing number of applications running on top of OpenStack infrastructure.
In an effort to avoid significant integration work that would be required if
each service produced a unique notification payload, we have defined a minimum
data set that provides the core data elements needed for downstream metering
processes. This format is not enforced by Ceilometer but serves as an advisory
guideline for PaaS service developers:

::

   [
    {
        "Field": "event_type",
        "Type": "enumeration",
        "Description": "for event type records, this describes the actual event that occurred",
        "Compliance": "required for events",
        "Notes": "depends on service, defaults to create, exists, delete"
    },
    {
        "Field": "timestamp",
        "Type": "UTC DateTime",
        "Description": "timestamp of when this event was generated at the resource",
        "Compliance": "required",
        "Notes": "ISO 8859 date YYYY-mm-ddThh:mm:ss"
    },
    {
        "Field": "message_id",
        "Type": "String",
        "Description": "unique identifier for event",
        "Compliance": "required",
        "Notes": ""
    },
    {
        "payload": [
        {
            "Field": "version",
            "Type": "String",
            "Description": "Version of event format",
            "Compliance": "required",
            "Notes": ""
        },
        {
            "Field": "audit_period_beginning",
            "Type": "UTC DateTime",
            "Description": "Represents start time for metrics reported",
            "Compliance": "required",
            "Notes": "Format ISO 8859 date YYYY-mm-ddThh:mm:ss"
        },
        {
            "Field": "audit_period_ending",
            "Type": "UTC DateTime",
            "Description": "Represents end time for metrics reported",
            "Compliance": "required",
            "Notes": "Format ISO 8859 date YYYY-mm-ddThh:mm:ss"
        },
        {
            "Field": "record_type",
            "Type": "enumeration ",
            "Values": {
                "event": "events describe some kind of state change in the service",
                "quantity": "quantity describes a usage metric value"
            },
            "Compliance": "optional",
            "Notes": ""
        },
        {
            "Field": "project_id",
            "Type": "UUID",
            "Description": "Keystone project_id identifies the owner of
                            the service instance",
            "Compliance": "required",
            "Notes": ""
        },
        {
            "Field": "user_id",
            "Type": "UUID",
            "Description": "Keystone user_id identifies specific user",
            "Compliance": "optional",
            "Notes": ""
        },
        {
            "Field": "service_id",
            "Type": "UUID",
            "Description": "Keystone service_id uniquely identifies a service",
            "Compliance": "required",
            "Notes": ""
        },
        {
            "Field": "service_type",
            "Type": "String",
            "Description": "Keystone service_type uniquely identifies a service",
            "Compliance": "required",
            "Notes": ""
        },
        {
            "Field": "instance_id",
            "Type": "UUID",
            "Description": "uniquely identifies an instance of the service",
            "Compliance": "required",
            "Notes": "assuming instance level reporting"
        },
        {
            "Field": "display_name",
            "Type": "String",
            "Description": "text description of service",
            "Compliance": "optional",
            "Notes": "used if customer names instances"
        },
        {
            "Field": "instance_type_id",
            "Type": "enumeration",
            "Description": "used to describe variations of a service",
            "Compliance": "required",
            "Notes": "needed if variations of service have different prices or
                      need to be broken out separately"
        },
        {
            "Field": "instance_type",
            "Type": "String",
            "Description": "text description of service variations",
            "Compliance": "optional",
            "Notes": ""
        },
        {
            "Field": "availability_zone",
            "Type": "String",
            "Description": "where the service is deployed",
            "Compliance": "optional",
            "Notes": "required if service is deployed at an AZ level"
        },
        {
            "Field": "region",
            "Type": "String",
            "Description": "data center that the service is deployed in",
            "Compliance": "optional",
            "Notes": "required if service is billed at a regional level"
        },
        {
            "Field": "state",
            "Type": "enumeration",
            "Description": "status of the service at the time of record generation",
            "Compliance": "optional",
            "Notes": "required for existence events"
        },
        {
            "Field": "state_description",
            "Type": "String",
            "Description": "text description of state of service",
            "Compliance": "",
            "Notes": ""
        },
        {
            "Field": "license_code",
            "Type": "enumeration",
            "Description": "value that describes a specific license model",
            "Compliance": "optional",
            "Notes": "this field is TBD depending on dev_pay design work"
        },
            {
                "metrics": [
                    {
                        "Field": "metric_name",
                        "Type": "String",
                        "Description": "unique name for the metric that is represented
                         in this record",
                        "Compliance": "required",
                        "Notes": ""
                    },
                    {
                        "Field": "metric_type",
                        "Type": "enumeration",
                        "Description": "gauge, cumulative, delta",
                        "Compliance": "required",
                        "Notes": "describes the behavior of the metric, from Ceilometer"
                    },
                    {
                        "Field": "metric_value",
                        "Type": "Float",
                        "Description": "value of metric for quantity type records",
                        "Compliance": "required for quantities",
                        "Notes": ""
                    },
                    {
                        "Field": "metric_units",
                        "Type": "enumeration",
                        "Description": "describes the units for the quantity",
                        "Compliance": "optional",
                        "Notes": ""
                    }
                ]
            }
        ]
    }
  ]


.. note::

    **Required** means that it must be present and described as in the specification.
    **Optional** indicates it can be present or not, but if present it must be described
    as in the specifications.
    **Audit period timestamps** are not currently enforced against the audit period.

Sample Events
=============

The event format listed above is used to deliver two basic types of events:
*quantity* and *state* events.

Sample state events
-------------------

These events describe the state of the metered service. They are very similar to
the existing state events generated by Infrastructure. Generally there would be at
least three types of events: create, exists and delete. Examples of these events for
a DNS service are listed below.

``dns.zone.create`` event is sent after a zone has been created::

    {
        "event_type": "dns.zone.create",
        "time_stamp": "2013-04-07 22:56:30.026191",
        "message_id": 52232791371,
        "payload": {
                "instance_type": "type1",
                "availability_zone": "az1",
                "instance_id": "6accc078-81de-4567-894f-53af5653ac63",
                "audit_period_beginning": "2013-04-07 21:56:32.249876",
                "state": "active",
                "audit_period_ending": "2013-04-07 22:56:32.249712",
                "service_id": "1abbb078-81cd-4758-974e-35fa5653ac63",
                "version": "1.0",
                "tenant_id": "12345",
                "instance_type_id": 1,
                "display_name": "example100.com",
                "message_id": 52232791371,
                "user_id": "6789",
                "state_description": "happy DNS"
                }
    }

``dns.zone.exists`` event is sent every hour for existing zones::

    {
        "event_type": "dns.zone.exists",
        "time_stamp": "2013-04-07 22:56:37.782573",
        "message_id": 52232791372,
        "payload": {
                "instance_type": "type1",
                "availability_zone": "az1",
                "instance_id": "6accc078-81de-4567-894f-53af5653ac63",
                "audit_period_beginning": "2013-04-07 21:56:37.783215",
                "state": "active",
                "audit_period_ending": "2013-04-07 22:56:37.783153",
                "service_id": "1abbb078-81cd-4758-974e-35fa5653ac63",
                "version": "1.0",
                "tenant_id": "12345",
                "instance_type_id": 1,
                "display_name": "example100.com",
                "message_id": 52232791371,
                "user_id": "6789",
                "state_description": "happy DNS"
                }
    }

The ``dns.zone.delete`` event is sent when a zone is deleted::

    {
        "event_type": "dns.zone.delete",
        "time_stamp": "2013-04-07 22:56:37.787774",
        "message_id": 52232791373,
        "payload": {
                "instance_type": "type1",
                "availability_zone": "az1",
                "instance_id": "6accc078-81de-4567-894f-53af5653ac63",
                "audit_period_beginning": "2013-04-07 21:56:37.788177",
                "state": "active",
                "audit_period_ending": "2013-04-07 22:56:37.788144",
                "service_id": "1abbb078-81cd-4758-974e-35fa5653ac63",
                "version": "1.0",
                "tenant_id": "12345",
                "instance_type_id": 1,
                "display_name": "example100.com",
                "message_id": 52232791371,
                "user_id": "6789",
                "state_description": "happy DNS"
                }
        }

Sample quantity events
----------------------
Quantity events have the same overall format, but additionally have a section
called metrics which is a section called metrics which is an array of
information about the meters that the event is reporting on. Each metric entry
has a type, unit, name and volume.  Multiple values can be reported in one
event.

``dns.zone.usage`` is hourly event sent with usage for each zone instance::

    {
        "event_type": "dns.zone.usage",
        "time_stamp": "2013-04-08 10:05:31.618074",
        "message_id": 52232791371,
        "payload": {
                "metrics": [
                    {
                     "metric_type": "delta",
                     "metric_value": 42,
                     "metric_units": "hits",
                     "metric_name": "queries"
                    }
                ],
                "instance_type": "type1",
                "availability_zone": "az1",
                "instance_id": "6accc078-81de-4567-894f-53af5653ac63",
                "audit_period_beginning": "2013-04-08 09:05:31.618204",
                "state": "active",
                "audit_period_ending": "2013-04-08 10:05:31.618191",
                "service_id": "1abbb078-81cd-4758-974e-35fa5653ac63",
                "version": "1.0",
                "tenant_id": "12345",
                "instance_type_id": 1,
                "display_name": "example100.com",
                "message_id": 52232791371,
                "user_id": "6789",
                "state_description": "happy DNS"
                }
    }
