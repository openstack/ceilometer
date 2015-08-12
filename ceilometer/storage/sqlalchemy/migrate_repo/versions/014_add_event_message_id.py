#
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

from migrate.changeset.constraint import UniqueConstraint
import sqlalchemy


def upgrade(migrate_engine):
    meta = sqlalchemy.MetaData(bind=migrate_engine)

    event = sqlalchemy.Table('event', meta, autoload=True)
    message_id = sqlalchemy.Column('message_id', sqlalchemy.String(50))
    event.create_column(message_id)

    cons = UniqueConstraint('message_id', table=event)
    cons.create()

    index = sqlalchemy.Index('idx_event_message_id', event.c.message_id)
    index.create(bind=migrate_engine)

    # Populate the new column ...
    trait = sqlalchemy.Table('trait', meta, autoload=True)
    unique_name = sqlalchemy.Table('unique_name', meta, autoload=True)
    join = trait.join(unique_name, unique_name.c.id == trait.c.name_id)
    traits = sqlalchemy.select([trait.c.event_id, trait.c.t_string],
                               whereclause=(unique_name.c.key == 'message_id'),
                               from_obj=join)

    for event_id, value in traits.execute():
        (event.update().where(event.c.id == event_id).values(message_id=value).
         execute())

    # Leave the Trait, makes the rollback easier and won't really hurt anyone.
