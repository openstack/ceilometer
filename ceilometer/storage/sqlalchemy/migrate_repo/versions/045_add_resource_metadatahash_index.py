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


# Add index on metadata_hash column of resource
def upgrade(migrate_engine):
    meta = sa.MetaData(bind=migrate_engine)
    resource = sa.Table('resource', meta, autoload=True)
    index = sa.Index('ix_resource_metadata_hash', resource.c.metadata_hash)
    index.create(bind=migrate_engine)
