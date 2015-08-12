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
import sqlalchemy as sa


class ForeignKeyHandle(object):
    def __init__(self, meta):
        sample = sa.Table('sample', meta, autoload=True)
        meter = sa.Table('meter', meta, autoload=True)
        self.sample_params = {'columns': [sample.c.meter_id],
                              'refcolumns': [meter.c.id]}
        if meta.bind.engine.name == 'mysql':
            self.sample_params['name'] = "fk_sample_meter_id"

    def __enter__(self):
        ForeignKeyConstraint(**self.sample_params).drop()

    def __exit__(self, type, value, traceback):
        ForeignKeyConstraint(**self.sample_params).create()


def upgrade(migrate_engine):
    if migrate_engine.name == 'sqlite':
        return
    meta = sa.MetaData(bind=migrate_engine)
    sample = sa.Table('sample', meta, autoload=True)

    with ForeignKeyHandle(meta):
        # remove stray indexes implicitly created by InnoDB
        for index in sample.indexes:
            if index.name in ['fk_sample_meter_id', 'fk_sample_resource_id']:
                index.drop()
        sa.Index('ix_sample_meter_id', sample.c.meter_id).create()
