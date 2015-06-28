# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    resource = Table('resource', meta, autoload=True)
    resource.c.user_id.alter(type=String(255))
    resource.c.project_id.alter(type=String(255))
    resource.c.resource_id.alter(type=String(255))
    resource.c.source_id.alter(type=String(255))
    sample = Table('sample', meta, autoload=True)
    sample.c.message_signature.alter(type=String(64))
    sample.c.message_id.alter(type=String(128))
    alarm = Table('alarm', meta, autoload=True)
    alarm.c.alarm_id.alter(type=String(128))
    alarm.c.user_id.alter(type=String(255))
    alarm.c.project_id.alter(type=String(255))
    alarm_history = Table('alarm_history', meta, autoload=True)
    alarm_history.c.alarm_id.alter(type=String(128))
    alarm_history.c.user_id.alter(type=String(255))
    alarm_history.c.project_id.alter(type=String(255))
    alarm_history.c.event_id.alter(type=String(128))
    alarm_history.c.on_behalf_of.alter(type=String(255))
