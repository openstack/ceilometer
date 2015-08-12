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

from sqlalchemy import Float
from sqlalchemy import MetaData
from sqlalchemy import Table


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    metadata_float = Table('metadata_float', meta, autoload=True)
    metadata_float.c.value.alter(type=Float(53))
    trait = Table('trait', meta, autoload=True)
    trait.c.t_float.alter(type=Float(53))
