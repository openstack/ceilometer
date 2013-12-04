#
# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
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

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy.sql import select
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Text

from ceilometer import utils

tables = [('metadata_text', Text, True),
          ('metadata_bool', Boolean, False),
          ('metadata_int', Integer, False),
          ('metadata_float', Float, False)]


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    meter = Table('meter', meta, autoload=True)
    meta_tables = {}
    for t_name, t_type, t_nullable in tables:
        meta_tables[t_name] = Table(
            t_name, meta,
            Column('id', Integer, ForeignKey('meter.id'), primary_key=True),
            Column('meta_key', String(255), index=True, primary_key=True),
            Column('value', t_type, nullable=t_nullable),
            mysql_engine='InnoDB',
            mysql_charset='utf8',
        )
        meta_tables[t_name].create()

    for row in select([meter]).execute():
        if row['resource_metadata']:
            meter_id = row['id']
            rmeta = json.loads(row['resource_metadata'])
            for key, v in utils.dict_to_keyval(rmeta):
                ins = None
                if isinstance(v, basestring) or v is None:
                    ins = meta_tables['metadata_text'].insert()
                elif isinstance(v, bool):
                    ins = meta_tables['metadata_bool'].insert()
                elif isinstance(v, (int, long)):
                    ins = meta_tables['metadata_int'].insert()
                elif isinstance(v, float):
                    ins = meta_tables['metadata_float'].insert()
                if ins is not None:
                    ins.values(id=meter_id, meta_key=key, value=v).execute()


def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    for t in tables:
        table = Table(t[0], meta, autoload=True)
        table.drop()
