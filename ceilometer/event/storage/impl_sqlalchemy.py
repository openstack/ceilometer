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

"""SQLAlchemy storage backend."""

from __future__ import absolute_import
import os

from oslo.config import cfg
from oslo.db.sqlalchemy import session as db_session

from ceilometer.storage import impl_sqlalchemy as base
from ceilometer import utils


AVAILABLE_CAPABILITIES = {
    'events': {'query': {'simple': True}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Put the event data into a SQLAlchemy database.

    """
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def __init__(self, url):
        self._engine_facade = db_session.EngineFacade(
            url,
            **dict(cfg.CONF.database.items())
        )

    def upgrade(self):
        # NOTE(gordc): to minimise memory, only import migration when needed
        from oslo.db.sqlalchemy import migration
        path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            '..', '..', 'storage', 'sqlalchemy',
                            'migrate_repo')
        migration.db_sync(self._engine_facade.get_engine(), path)
