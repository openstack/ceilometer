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
import hashlib

import migrate
from oslo_serialization import jsonutils
import sqlalchemy as sa


m_tables = [('metadata_text', sa.Text, True),
            ('metadata_bool', sa.Boolean, False),
            ('metadata_int', sa.BigInteger, False),
            ('metadata_float', sa.Float(53), False)]


def _migrate_meta_tables(meta, col, new_col, new_fk):
    for t_name, t_type, t_nullable in m_tables:
        m_table = sa.Table(t_name, meta, autoload=True)
        m_table_new = sa.Table(
            '%s_new' % t_name, meta,
            sa.Column('id', sa.Integer, sa.ForeignKey(new_fk),
                      primary_key=True),
            sa.Column('meta_key', sa.String(255),
                      primary_key=True),
            sa.Column('value', t_type, nullable=t_nullable),
            mysql_engine='InnoDB',
            mysql_charset='utf8',
        )
        m_table_new.create()

        if m_table.select().scalar() is not None:
            m_table_new.insert().from_select(
                ['id', 'meta_key', 'value'],
                sa.select([new_col, m_table.c.meta_key,
                           m_table.c.value]).where(
                    col == m_table.c.id).group_by(
                    new_col, m_table.c.meta_key, m_table.c.value)).execute()

        m_table.drop()
        if meta.bind.engine.name != 'sqlite':
            sa.Index('ix_%s_meta_key' % t_name,
                     m_table_new.c.meta_key).create()
        m_table_new.rename(t_name)


def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    resource = sa.Table(
        'resource', meta,
        sa.Column('internal_id', sa.Integer, primary_key=True),
        sa.Column('resource_id', sa.String(255)),
        sa.Column('user_id', sa.String(255)),
        sa.Column('project_id', sa.String(255)),
        sa.Column('source_id', sa.String(255)),
        sa.Column('resource_metadata', sa.Text),
        sa.Column('metadata_hash', sa.String(32)),
        mysql_engine='InnoDB',
        mysql_charset='utf8')
    resource.create()

    # copy resource data in to resource table
    sample = sa.Table('sample', meta, autoload=True)
    sa.Column('metadata_hash', sa.String(32)).create(sample)
    for row in sa.select([sample.c.id, sample.c.resource_metadata]).execute():
        sample.update().where(sample.c.id == row['id']).values(
            {sample.c.metadata_hash:
             hashlib.md5(jsonutils.dumps(
                 row['resource_metadata'],
                 sort_keys=True)).hexdigest()}).execute()
    query = sa.select([sample.c.resource_id, sample.c.user_id,
                       sample.c.project_id, sample.c.source_id,
                       sample.c.resource_metadata,
                       sample.c.metadata_hash]).distinct()
    for row in query.execute():
        resource.insert().values(
            resource_id=row['resource_id'],
            user_id=row['user_id'],
            project_id=row['project_id'],
            source_id=row['source_id'],
            resource_metadata=row['resource_metadata'],
            metadata_hash=row['metadata_hash']).execute()
    # link sample records to new resource records
    sa.Column('resource_id_new', sa.Integer).create(sample)
    for row in sa.select([resource]).execute():
        (sample.update().
         where(sa.and_(
             sample.c.resource_id == row['resource_id'],
             sample.c.user_id == row['user_id'],
             sample.c.project_id == row['project_id'],
             sample.c.source_id == row['source_id'],
             sample.c.metadata_hash == row['metadata_hash'])).
         values({sample.c.resource_id_new: row['internal_id']}).execute())

    sample.c.resource_id.drop()
    sample.c.metadata_hash.drop()
    sample.c.resource_id_new.alter(name='resource_id')
    # re-bind metadata to pick up alter name change
    meta = sa.MetaData(bind=migrate_engine)
    sample = sa.Table('sample', meta, autoload=True)
    resource = sa.Table('resource', meta, autoload=True)
    if migrate_engine.name != 'sqlite':
        sa.Index('ix_resource_resource_id', resource.c.resource_id).create()
        sa.Index('ix_sample_user_id', sample.c.user_id).drop()
        sa.Index('ix_sample_project_id', sample.c.project_id).drop()
        sa.Index('ix_sample_resource_id', sample.c.resource_id).create()
        sa.Index('ix_sample_meter_id_resource_id',
                 sample.c.meter_id, sample.c.resource_id).create()

        params = {'columns': [sample.c.resource_id],
                  'refcolumns': [resource.c.internal_id]}
        if migrate_engine.name == 'mysql':
            params['name'] = 'fk_sample_resource_internal_id'
        migrate.ForeignKeyConstraint(**params).create()

    sample.c.user_id.drop()
    sample.c.project_id.drop()
    sample.c.source_id.drop()
    sample.c.resource_metadata.drop()

    _migrate_meta_tables(meta, sample.c.id, sample.c.resource_id,
                         'resource.internal_id')
