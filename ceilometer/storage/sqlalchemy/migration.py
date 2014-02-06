# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
#         Julien Danjou <julien@danjou.info>
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

import os

from alembic import config as alembic_config
from migrate import exceptions as versioning_exceptions
from migrate.versioning import api as versioning_api
from migrate.versioning.repository import Repository
import sqlalchemy

_REPOSITORY = None


def db_sync(engine):
    db_version(engine)  # This is needed to create a version stamp in empty DB
    repository = _find_migrate_repo()
    versioning_api.upgrade(engine, repository)
    config = _alembic_config()
    config._engine = engine


def _alembic_config():
    path = os.path.join(os.path.dirname(__file__), 'alembic/alembic.ini')
    config = alembic_config.Config(path)
    return config


def db_version(engine):
    repository = _find_migrate_repo()
    try:
        return versioning_api.db_version(engine,
                                         repository)
    except versioning_exceptions.DatabaseNotControlledError:
        meta = sqlalchemy.MetaData()
        meta.reflect(bind=engine)
        tables = meta.tables
        if not tables:
            db_version_control(engine, 0)
            return versioning_api.db_version(engine, repository)


def db_version_control(engine, version=None):
    repository = _find_migrate_repo()
    versioning_api.version_control(engine, repository, version)
    return version


def _find_migrate_repo():
    """Get the path for the migrate repository."""
    global _REPOSITORY
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                        'migrate_repo')
    assert os.path.exists(path)
    if _REPOSITORY is None:
        _REPOSITORY = Repository(path)
    return _REPOSITORY


def paged(query, size=1000):
    """Page query results

    :param query: the SQLAlchemy query to execute
    :param size: the max page size
    return: generator with query data
    """
    offset = 0
    while True:
        page = query.offset(offset).limit(size).execute()
        if page.rowcount <= 0:
            # There are no more rows
            break
        for row in page:
            yield row
        offset += size
