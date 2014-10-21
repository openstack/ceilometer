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

import sqlalchemy as sa

from ceilometer.storage.sqlalchemy import models

tables = [('trait_text', sa.Text, True, 't_string', 1),
          ('trait_int', sa.Integer, False, 't_int', 2),
          ('trait_float', sa.Float, False, 't_float', 3),
          ('trait_datetime', models.PreciseTimestamp(),
           False, 't_datetime', 4)]


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    trait = sa.Table('trait', meta, autoload=True)
    event = sa.Table('event', meta, autoload=True)
    trait_type = sa.Table('trait_type', meta, autoload=True)
    for t_name, t_type, t_nullable, col_name, __ in tables:
        t_table = sa.Table(
            t_name, meta,
            sa.Column('event_id', sa.Integer,
                      sa.ForeignKey(event.c.id), primary_key=True),
            sa.Column('key', sa.String(255), primary_key=True),
            sa.Column('value', t_type, nullable=t_nullable),
            sa.Index('ix_%s_event_id_key' % t_name,
                     'event_id', 'key'),
            mysql_engine='InnoDB',
            mysql_charset='utf8',
        )
        t_table.create()
        query = sa.select(
            [trait.c.event_id,
             trait_type.c.desc,
             trait.c[col_name]]).select_from(
                 trait.join(trait_type,
                            trait.c.trait_type_id == trait_type.c.id)).where(
                                trait.c[col_name] != sa.null())
        if query.alias().select().scalar() is not None:
            t_table.insert().from_select(
                ['event_id', 'key', 'value'], query).execute()
    trait.drop()
    trait_type.drop()


def downgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    event = sa.Table('event', meta, autoload=True)
    trait_type = sa.Table(
        'trait_type', meta,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('desc', sa.String(255)),
        sa.Column('data_type', sa.Integer),
        sa.UniqueConstraint('desc', 'data_type', name='tt_unique'),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    trait_type.create()
    trait = sa.Table(
        'trait', meta,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('trait_type_id', sa.Integer, sa.ForeignKey(trait_type.c.id)),
        sa.Column('event_id', sa.Integer, sa.ForeignKey(event.c.id)),
        sa.Column('t_string', sa.String(255), nullable=True, default=None),
        sa.Column('t_float', sa.Float(53), nullable=True, default=None),
        sa.Column('t_int', sa.Integer, nullable=True, default=None),
        sa.Column('t_datetime', models.PreciseTimestamp(), nullable=True,
                  default=None),
        sa.Index('ix_trait_t_int', 't_int'),
        sa.Index('ix_trait_t_string', 't_string'),
        sa.Index('ix_trait_t_datetime', 't_datetime'),
        sa.Index('ix_trait_t_float', 't_float'),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    trait.create()

    for t_name, __, __, col_name, type_id in tables:
        table = sa.Table(t_name, meta, autoload=True)
        trait_type.insert().from_select([trait_type.c.desc,
                                         trait_type.c.data_type],
                                        sa.select([table.c.key,
                                                   type_id])
                                        .distinct()).execute()
        trait.insert().from_select([trait.c['event_id'],
                                    trait.c['trait_type_id'],
                                    trait.c[col_name]],
                                   sa.select([table.c.event_id,
                                              trait_type.c.id,
                                              table.c.value])
                                   .select_from(
                                       table.join(
                                           trait_type,
                                           table.c.key == trait_type.c.desc))
                                   ).execute()
        table.drop()
