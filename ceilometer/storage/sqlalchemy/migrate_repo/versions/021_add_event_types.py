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
from migrate import ForeignKeyConstraint
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import select
from sqlalchemy import String
from sqlalchemy import Table

from ceilometer.storage.sqlalchemy import migration


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    event_type = Table(
        'event_type', meta,
        Column('id', Integer, primary_key=True),
        Column('desc', String(255), unique=True),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    event_type.create()
    event = Table('event', meta, autoload=True)
    unique_name = Table('unique_name', meta, autoload=True)

    # Event type is a specialization of Unique name, so
    # we insert into the event_type table all the distinct
    # unique names from the event.unique_name field along
    # with the key from the unique_name table, and
    # then rename the event.unique_name field to event.event_type
    conn = migrate_engine.connect()
    sql = ("INSERT INTO event_type "
           "SELECT unique_name.id, unique_name.key FROM event "
           "INNER JOIN unique_name "
           "ON event.unique_name_id = unique_name.id "
           "GROUP BY unique_name.id")
    conn.execute(sql)
    conn.close()
    # Now we need to drop the foreign key constraint, rename
    # the event.unique_name column, and re-add a new foreign
    # key constraint
    params = {'columns': [event.c.unique_name_id],
              'refcolumns': [unique_name.c.id]}
    if migrate_engine.name == 'mysql':
        params['name'] = "event_ibfk_1"
    fkey = ForeignKeyConstraint(**params)
    fkey.drop()

    Column('event_type_id', Integer).create(event)

    # Move data from unique_name_id column into event_type_id column
    # and delete the entry from the unique_name table
    query = select([event.c.id, event.c.unique_name_id])
    for key, value in migration.paged(query):
        (event.update().where(event.c.id == key).
         values({"event_type_id": value}).execute())
        unique_name.delete().where(unique_name.c.id == key).execute()

    params = {'columns': [event.c.event_type_id],
              'refcolumns': [event_type.c.id]}
    if migrate_engine.name == 'mysql':
        params['name'] = "_".join(('fk', 'event_type', 'id'))
    fkey = ForeignKeyConstraint(**params)
    fkey.create()

    event.c.unique_name_id.drop()
