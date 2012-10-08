..
      Copyright 2012 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=======================
 Configuration Options
=======================

The following table lists the ceilometer specific option in the global configuration file.
Please note that ceilometer uses openstack-common extensively, which requires that
the other parameters are set appropriately. If you use sql alchemy, it's specific
paramater will need to be set.


==========================  ====================================  ==============================================================
Parameter                   Default                               Note
==========================  ====================================  ==============================================================
nova_control_exchange       nova                                  Exchange name for Nova notifications
glance_control_exchange     glance_notifications                  Exchange name for Glance notifications
glance_registry_host        localhost                             URL of Glance API server
glance_registry_port        9191                                  port of Glance API server
cinder_control_exchange     cinder                                Exchange name for Cinder notifications
quantum_control_exchange    quantum                               Exchange name for Quantum notifications
metering_secret             change this or be hacked              Secret value for signing metering messages
metering_topic              metering                              the topic ceilometer uses for metering messages
control_exchange            ceilometer                            AMQP exchange to connect to if using RabbitMQ or Qpid
periodic_interval           600                                   seconds between running periodic tasks
os-username                 glance                                Username to use for openstack service access
os-password                 admin                                 Password to use for openstack service access
os-tenant-id                                                      Tenant ID to use for openstack service access
os-tenant-name              admin                                 Tenant name to use for openstack service access
os-auth-url                 http://localhost:5000/v2.0            Auth URL to use for openstack service access
database_connection         mongodb://localhost:27017/ceilometer  Database connection string
metering_api_port           9000                                  The port for the ceilometer API server
================================================================================================================================
SQL Alchemy
================================================================================================================================
sql_connection_debug        0                                     Verbosity of SQL debugging information. 0=None, 100=Everything
sql_connection_trace        False                                 Add python stack traces to SQL as comment strings
sql_idle_timeout            3600                                  timeout before idle sql connections are reaped
sql_max_retries             10                                    maximum db connection retries during startup.
                                                                  (setting -1 implies an infinite retry count)
sql_retry_interval          10                                    interval between retries of opening a sql connection
mysql_engine                InnoDB                                MySQL engine to use
sqlite_synchronous          True                                  If passed, use synchronous mode for sqlite
==========================  ====================================  ==============================================================

