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

from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)

    unique_name = Table(
        'unique_name', meta,
        Column('id', Integer, primary_key=True),
        Column('key', String(32), index=True),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    unique_name.create()

    event = Table(
        'event', meta,
        Column('id', Integer, primary_key=True),
        Column('generated', Float(asdecimal=True), index=True),
        Column('unique_name_id', Integer, ForeignKey('unique_name.id')),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    event.create()

    trait = Table(
        'trait', meta,
        Column('id', Integer, primary_key=True),
        Column('name_id', Integer, ForeignKey('unique_name.id')),
        Column('t_type', Integer, index=True),
        Column('t_string', String(32), nullable=True, default=None,
               index=True),
        Column('t_float', Float, nullable=True, default=None, index=True),
        Column('t_int', Integer, nullable=True, default=None, index=True),
        Column('t_datetime', Float(asdecimal=True), nullable=True,
               default=None, index=True),
        Column('event_id', Integer, ForeignKey('event.id')),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    trait.create()
