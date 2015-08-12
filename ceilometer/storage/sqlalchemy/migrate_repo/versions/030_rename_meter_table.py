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


def _handle_meter_indices(meta):
    if meta.bind.engine.name == 'sqlite':
        return

    resource = sa.Table('resource', meta, autoload=True)
    project = sa.Table('project', meta, autoload=True)
    user = sa.Table('user', meta, autoload=True)
    meter = sa.Table('meter', meta, autoload=True)

    indices = [(sa.Index('ix_meter_timestamp', meter.c.timestamp),
                sa.Index('ix_sample_timestamp', meter.c.timestamp)),
               (sa.Index('ix_meter_user_id', meter.c.user_id),
                sa.Index('ix_sample_user_id', meter.c.user_id)),
               (sa.Index('ix_meter_project_id', meter.c.project_id),
                sa.Index('ix_sample_project_id', meter.c.project_id)),
               (sa.Index('idx_meter_rid_cname', meter.c.resource_id,
                         meter.c.counter_name),
                sa.Index('idx_sample_rid_cname', meter.c.resource_id,
                         meter.c.counter_name))]

    fk_params = [({'columns': [meter.c.resource_id],
                   'refcolumns': [resource.c.id]},
                  'fk_meter_resource_id',
                  'fk_sample_resource_id'),
                 ({'columns': [meter.c.project_id],
                   'refcolumns': [project.c.id]},
                  'fk_meter_project_id',
                  'fk_sample_project_id'),
                 ({'columns': [meter.c.user_id],
                   'refcolumns': [user.c.id]},
                  'fk_meter_user_id',
                  'fk_sample_user_id')]

    for fk in fk_params:
        params = fk[0]
        if meta.bind.engine.name == 'mysql':
            params['name'] = fk[1]
        migrate.ForeignKeyConstraint(**params).drop()

    for meter_ix, sample_ix in indices:
        meter_ix.drop()
        sample_ix.create()

    for fk in fk_params:
        params = fk[0]
        if meta.bind.engine.name == 'mysql':
            params['name'] = fk[2]
        migrate.ForeignKeyConstraint(**params).create()


def _alter_sourceassoc(meta, t_name, ix_name, post_action=False):
    if meta.bind.engine.name == 'sqlite':
        return

    sourceassoc = sa.Table('sourceassoc', meta, autoload=True)
    table = sa.Table(t_name, meta, autoload=True)
    user = sa.Table('user', meta, autoload=True)

    c_name = '%s_id' % t_name
    col = getattr(sourceassoc.c, c_name)
    uniq_name = 'uniq_sourceassoc0%s0user_id' % c_name

    uniq_cols = (c_name, 'user_id')
    param = {'columns': [col],
             'refcolumns': [table.c.id]}
    user_param = {'columns': [sourceassoc.c.user_id],
                  'refcolumns': [user.c.id]}
    if meta.bind.engine.name == 'mysql':
        param['name'] = 'fk_sourceassoc_%s' % c_name
        user_param['name'] = 'fk_sourceassoc_user_id'

    actions = [migrate.ForeignKeyConstraint(**user_param),
               migrate.ForeignKeyConstraint(**param),
               sa.Index(ix_name, sourceassoc.c.source_id, col),
               migrate.UniqueConstraint(*uniq_cols, table=sourceassoc,
                                        name=uniq_name)]
    for action in actions:
        action.create() if post_action else action.drop()


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)

    _handle_meter_indices(meta)
    meter = sa.Table('meter', meta, autoload=True)
    meter.rename('sample')

    _alter_sourceassoc(meta, 'meter', 'idx_sm')
    sourceassoc = sa.Table('sourceassoc', meta, autoload=True)
    sourceassoc.c.meter_id.alter(name='sample_id')
    # re-bind metadata to pick up alter name change
    meta = sa.MetaData(bind=migrate_engine)
    _alter_sourceassoc(meta, 'sample', 'idx_ss', True)
