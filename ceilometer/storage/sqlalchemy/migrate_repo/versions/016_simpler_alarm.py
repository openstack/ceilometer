# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
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

import json

from sqlalchemy import MetaData, Table, Column, Index
from sqlalchemy import String, Float, Integer, Text


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    table = Table('alarm', meta, autoload=True)

    type = Column('type', String(50), default='threshold')
    type.create(table, populate_default=True)

    rule = Column('rule', Text())
    rule.create(table)

    for row in table.select().execute().fetchall():
        query = []
        if row.matching_metadata is not None:
            matching_metadata = json.loads(row.matching_metadata)
            for key in matching_metadata:
                query.append({'field': key,
                              'op': 'eq',
                              'value': matching_metadata[key]})
        rule = {
            'meter_name': row.meter_name,
            'comparison_operator': row.comparison_operator,
            'threshold': row.threshold,
            'statistic': row.statistic,
            'evaluation_periods': row.evaluation_periods,
            'period': row.period,
            'query': query
        }
        table.update().where(table.c.id == row.id).values(rule=rule).execute()

    index = Index('ix_alarm_counter_name', table.c.meter_name)
    index.drop(bind=migrate_engine)
    table.c.meter_name.drop()
    table.c.comparison_operator.drop()
    table.c.threshold.drop()
    table.c.statistic.drop()
    table.c.evaluation_periods.drop()
    table.c.period.drop()
    table.c.matching_metadata.drop()


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    table = Table('alarm', meta, autoload=True)

    columns = [
        Column('meter_name', String(255)),
        Column('comparison_operator', String(2)),
        Column('threshold', Float),
        Column('statistic', String(255)),
        Column('evaluation_periods', Integer),
        Column('period', Integer),
        Column('matching_metadata', Text())
    ]
    for c in columns:
        c.create(table)

    for row in table.select().execute().fetchall():
        if row.type != 'threshold':
            #note: type insupported in previous version
            table.delete().where(table.c.id == row.id).execute()
        else:
            rule = json.loads(row.rule)
            values = {'comparison_operator': rule['comparison_operator'],
                      'threshold': float(rule['threshold']),
                      'statistic': rule['statistic'],
                      'evaluation_periods': int(rule['evaluation_periods']),
                      'period': int(rule['period']),
                      'meter_name': int(rule['mater_name']),
                      'matching_metadata': {}}

            #note: op are ignored because previous format don't support it
            for q in rule['query']:
                values['matching_metadata'][q['field']] = q['value']
            values['matching_metadata'] = json.dumps(
                values['matching_metadata'])
            table.update().where(table.c.id == row.id
                                 ).values(**values).execute()

    index = Index('ix_alarm_counter_name', table.c.meter_name)
    index.create(bind=migrate_engine)

    table.c.type.drop()
    table.c.rule.drop()
