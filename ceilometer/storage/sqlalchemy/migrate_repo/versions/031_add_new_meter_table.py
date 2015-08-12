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
import migrate
import sqlalchemy as sa


def handle_rid_index(meta):
    if meta.bind.engine.name == 'sqlite':
        return

    resource = sa.Table('resource', meta, autoload=True)
    sample = sa.Table('sample', meta, autoload=True)
    params = {'columns': [sample.c.resource_id],
              'refcolumns': [resource.c.id],
              'name': 'fk_sample_resource_id'}
    if meta.bind.engine.name == 'mysql':
        # For mysql dialect all dependent FK should be removed
        #  before index create/delete
        migrate.ForeignKeyConstraint(**params).drop()

    index = sa.Index('idx_sample_rid_cname', sample.c.resource_id,
                     sample.c.counter_name)
    index.drop()

    if meta.bind.engine.name == 'mysql':
        migrate.ForeignKeyConstraint(**params).create()


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    meter = sa.Table(
        'meter', meta,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(255)),
        sa.Column('unit', sa.String(255)),
        sa.UniqueConstraint('name', 'type', 'unit', name='def_unique'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )
    meter.create()
    sample = sa.Table('sample', meta, autoload=True)
    query = sa.select([sample.c.counter_name, sample.c.counter_type,
                       sample.c.counter_unit]).distinct()
    for row in query.execute():
        meter.insert().values(name=row['counter_name'],
                              type=row['counter_type'],
                              unit=row['counter_unit']).execute()

    meter_id = sa.Column('meter_id', sa.Integer)
    meter_id.create(sample)
    params = {'columns': [sample.c.meter_id],
              'refcolumns': [meter.c.id]}
    if migrate_engine.name == 'mysql':
        params['name'] = 'fk_sample_meter_id'
    if migrate_engine.name != 'sqlite':
        migrate.ForeignKeyConstraint(**params).create()

    index = sa.Index('ix_meter_name', meter.c.name)
    index.create(bind=migrate_engine)

    for row in sa.select([meter]).execute():
        (sample.update().
         where(sa.and_(sample.c.counter_name == row['name'],
                       sample.c.counter_type == row['type'],
                       sample.c.counter_unit == row['unit'])).
         values({sample.c.meter_id: row['id']}).execute())

    handle_rid_index(meta)

    sample.c.counter_name.drop()
    sample.c.counter_type.drop()
    sample.c.counter_unit.drop()
    sample.c.counter_volume.alter(name='volume')
