#
# Copyright 2013 Red Hat, Inc.
#
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

from migrate import ForeignKeyConstraint
from sqlalchemy import MetaData, Table, Column, Index
from sqlalchemy import String, DateTime


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    project = Table('project', meta, autoload=True)
    user = Table('user', meta, autoload=True)

    alarm_history = Table(
        'alarm_history', meta,
        Column('event_id', String(255), primary_key=True, index=True),
        Column('alarm_id', String(255)),
        Column('on_behalf_of', String(255)),
        Column('project_id', String(255)),
        Column('user_id', String(255)),
        Column('type', String(20)),
        Column('detail', String(255)),
        Column('timestamp', DateTime(timezone=False)),
        mysql_engine='InnoDB',
        mysql_charset='utf8')

    alarm_history.create()

    if migrate_engine.name in ['mysql', 'postgresql']:
        indices = [Index('ix_alarm_history_alarm_id',
                         alarm_history.c.alarm_id),
                   Index('ix_alarm_history_on_behalf_of',
                         alarm_history.c.on_behalf_of),
                   Index('ix_alarm_history_project_id',
                         alarm_history.c.project_id),
                   Index('ix_alarm_history_on_user_id',
                         alarm_history.c.user_id)]

        for index in indices:
            index.create(migrate_engine)

        fkeys = [ForeignKeyConstraint(columns=[alarm_history.c.on_behalf_of],
                                      refcolumns=[project.c.id]),
                 ForeignKeyConstraint(columns=[alarm_history.c.project_id],
                                      refcolumns=[project.c.id]),
                 ForeignKeyConstraint(columns=[alarm_history.c.user_id],
                                      refcolumns=[user.c.id])]
        for fkey in fkeys:
            fkey.create(engine=migrate_engine)
