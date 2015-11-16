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
import datetime
import os

from oslo_config import cfg
from oslo_db.sqlalchemy import session as db_session
from oslo_log import log
from oslo_utils import timeutils
from sqlalchemy import desc

from ceilometer.alarm.storage import base
from ceilometer.alarm.storage import models as alarm_api_models
from ceilometer.i18n import _LI
from ceilometer import storage
from ceilometer.storage.sqlalchemy import models
from ceilometer.storage.sqlalchemy import utils as sql_utils
from ceilometer import utils

LOG = log.getLogger(__name__)

AVAILABLE_CAPABILITIES = {
    'alarms': {'query': {'simple': True,
                         'complex': True},
               'history': {'query': {'simple': True,
                                     'complex': True}}},
}


AVAILABLE_STORAGE_CAPABILITIES = {
    'storage': {'production_ready': True},
}


class Connection(base.Connection):
    """Put the data into a SQLAlchemy database.

    Tables::

        - meter
          - meter definition
          - { id: meter def id
              name: meter name
              type: meter type
              unit: meter unit
              }
        - sample
          - the raw incoming data
          - { id: sample id
              meter_id: meter id            (->meter.id)
              user_id: user uuid
              project_id: project uuid
              resource_id: resource uuid
              source_id: source id
              resource_metadata: metadata dictionaries
              volume: sample volume
              timestamp: datetime
              message_signature: message signature
              message_id: message uuid
              }
    """
    CAPABILITIES = utils.update_nested(base.Connection.CAPABILITIES,
                                       AVAILABLE_CAPABILITIES)
    STORAGE_CAPABILITIES = utils.update_nested(
        base.Connection.STORAGE_CAPABILITIES,
        AVAILABLE_STORAGE_CAPABILITIES,
    )

    def __init__(self, url):
        # Set max_retries to 0, since oslo.db in certain cases may attempt
        # to retry making the db connection retried max_retries ^ 2 times
        # in failure case and db reconnection has already been implemented
        # in storage.__init__.get_connection_from_config function
        options = dict(cfg.CONF.database.items())
        options['max_retries'] = 0
        # oslo.db doesn't support options defined by Ceilometer
        for opt in storage.OPTS:
            options.pop(opt.name, None)
        self._engine_facade = db_session.EngineFacade(url, **options)

    def upgrade(self):
        # NOTE(gordc): to minimise memory, only import migration when needed
        from oslo_db.sqlalchemy import migration
        path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                            '..', '..', 'storage', 'sqlalchemy',
                            'migrate_repo')
        migration.db_sync(self._engine_facade.get_engine(), path)

    def clear(self):
        engine = self._engine_facade.get_engine()
        for table in reversed(models.Base.metadata.sorted_tables):
            engine.execute(table.delete())
        engine.dispose()

    def _retrieve_data(self, filter_expr, orderby, limit, table):
        if limit == 0:
            return []

        session = self._engine_facade.get_session()
        engine = self._engine_facade.get_engine()
        query = session.query(table)
        transformer = sql_utils.QueryTransformer(table, query,
                                                 dialect=engine.dialect.name)
        if filter_expr is not None:
            transformer.apply_filter(filter_expr)

        transformer.apply_options(orderby,
                                  limit)

        retrieve = {models.Alarm: self._retrieve_alarms,
                    models.AlarmChange: self._retrieve_alarm_history}
        return retrieve[table](transformer.get_query())

    @staticmethod
    def _row_to_alarm_model(row):
        return alarm_api_models.Alarm(alarm_id=row.alarm_id,
                                      enabled=row.enabled,
                                      type=row.type,
                                      name=row.name,
                                      description=row.description,
                                      timestamp=row.timestamp,
                                      user_id=row.user_id,
                                      project_id=row.project_id,
                                      state=row.state,
                                      state_timestamp=row.state_timestamp,
                                      ok_actions=row.ok_actions,
                                      alarm_actions=row.alarm_actions,
                                      insufficient_data_actions=(
                                          row.insufficient_data_actions),
                                      rule=row.rule,
                                      time_constraints=row.time_constraints,
                                      repeat_actions=row.repeat_actions,
                                      severity=row.severity)

    def _retrieve_alarms(self, query):
        return (self._row_to_alarm_model(x) for x in query.all())

    def get_alarms(self, name=None, user=None, state=None, meter=None,
                   project=None, enabled=None, alarm_id=None,
                   alarm_type=None, severity=None):
        """Yields a lists of alarms that match filters.

        :param name: Optional name for alarm.
        :param user: Optional ID for user that owns the resource.
        :param state: Optional string for alarm state.
        :param meter: Optional string for alarms associated with meter.
        :param project: Optional ID for project that owns the resource.
        :param enabled: Optional boolean to list disable alarm.
        :param alarm_id: Optional alarm_id to return one alarm.
        :param alarm_type: Optional alarm type.
        :param severity: Optional alarm severity
        """

        session = self._engine_facade.get_session()
        query = session.query(models.Alarm)
        if name is not None:
            query = query.filter(models.Alarm.name == name)
        if enabled is not None:
            query = query.filter(models.Alarm.enabled == enabled)
        if user is not None:
            query = query.filter(models.Alarm.user_id == user)
        if project is not None:
            query = query.filter(models.Alarm.project_id == project)
        if alarm_id is not None:
            query = query.filter(models.Alarm.alarm_id == alarm_id)
        if state is not None:
            query = query.filter(models.Alarm.state == state)
        if alarm_type is not None:
            query = query.filter(models.Alarm.type == alarm_type)
        if severity is not None:
            query = query.filter(models.Alarm.severity == severity)

        query = query.order_by(desc(models.Alarm.timestamp))
        alarms = self._retrieve_alarms(query)

        # TODO(cmart): improve this by using sqlalchemy.func factory
        if meter is not None:
            alarms = filter(lambda row:
                            row.rule.get('meter_name', None) == meter,
                            alarms)

        return alarms

    def create_alarm(self, alarm):
        """Create an alarm.

        :param alarm: The alarm to create.
        """
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_row = models.Alarm(alarm_id=alarm.alarm_id)
            alarm_row.update(alarm.as_dict())
            session.add(alarm_row)

        return self._row_to_alarm_model(alarm_row)

    def update_alarm(self, alarm):
        """Update an alarm.

        :param alarm: the new Alarm to update
        """
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_row = session.merge(models.Alarm(alarm_id=alarm.alarm_id))
            alarm_row.update(alarm.as_dict())

        return self._row_to_alarm_model(alarm_row)

    def delete_alarm(self, alarm_id):
        """Delete an alarm and its history data.

        :param alarm_id: ID of the alarm to delete
        """
        session = self._engine_facade.get_session()
        with session.begin():
            session.query(models.Alarm).filter(
                models.Alarm.alarm_id == alarm_id).delete()
            # FIXME(liusheng): we should use delete cascade
            session.query(models.AlarmChange).filter(
                models.AlarmChange.alarm_id == alarm_id).delete()

    @staticmethod
    def _row_to_alarm_change_model(row):
        return alarm_api_models.AlarmChange(event_id=row.event_id,
                                            alarm_id=row.alarm_id,
                                            type=row.type,
                                            detail=row.detail,
                                            user_id=row.user_id,
                                            project_id=row.project_id,
                                            on_behalf_of=row.on_behalf_of,
                                            timestamp=row.timestamp)

    def query_alarms(self, filter_expr=None, orderby=None, limit=None):
        """Yields a lists of alarms that match filter."""
        return self._retrieve_data(filter_expr, orderby, limit, models.Alarm)

    def _retrieve_alarm_history(self, query):
        return (self._row_to_alarm_change_model(x) for x in query.all())

    def query_alarm_history(self, filter_expr=None, orderby=None, limit=None):
        """Return an iterable of model.AlarmChange objects."""
        return self._retrieve_data(filter_expr,
                                   orderby,
                                   limit,
                                   models.AlarmChange)

    def get_alarm_changes(self, alarm_id, on_behalf_of,
                          user=None, project=None, alarm_type=None,
                          severity=None, start_timestamp=None,
                          start_timestamp_op=None, end_timestamp=None,
                          end_timestamp_op=None):
        """Yields list of AlarmChanges describing alarm history

        Changes are always sorted in reverse order of occurrence, given
        the importance of currency.

        Segregation for non-administrative users is done on the basis
        of the on_behalf_of parameter. This allows such users to have
        visibility on both the changes initiated by themselves directly
        (generally creation, rule changes, or deletion) and also on those
        changes initiated on their behalf by the alarming service (state
        transitions after alarm thresholds are crossed).

        :param alarm_id: ID of alarm to return changes for
        :param on_behalf_of: ID of tenant to scope changes query (None for
                             administrative user, indicating all projects)
        :param user: Optional ID of user to return changes for
        :param project: Optional ID of project to return changes for
        :param alarm_type: Optional change type
        :param severity: Optional alarm severity
        :param start_timestamp: Optional modified timestamp start range
        :param start_timestamp_op: Optional timestamp start range operation
        :param end_timestamp: Optional modified timestamp end range
        :param end_timestamp_op: Optional timestamp end range operation
        """
        session = self._engine_facade.get_session()
        query = session.query(models.AlarmChange)
        query = query.filter(models.AlarmChange.alarm_id == alarm_id)

        if on_behalf_of is not None:
            query = query.filter(
                models.AlarmChange.on_behalf_of == on_behalf_of)
        if user is not None:
            query = query.filter(models.AlarmChange.user_id == user)
        if project is not None:
            query = query.filter(models.AlarmChange.project_id == project)
        if alarm_type is not None:
            query = query.filter(models.AlarmChange.type == alarm_type)
        if severity is not None:
            query = query.filter(models.AlarmChange.severity == severity)
        if start_timestamp:
            if start_timestamp_op == 'gt':
                query = query.filter(
                    models.AlarmChange.timestamp > start_timestamp)
            else:
                query = query.filter(
                    models.AlarmChange.timestamp >= start_timestamp)
        if end_timestamp:
            if end_timestamp_op == 'le':
                query = query.filter(
                    models.AlarmChange.timestamp <= end_timestamp)
            else:
                query = query.filter(
                    models.AlarmChange.timestamp < end_timestamp)

        query = query.order_by(desc(models.AlarmChange.timestamp))
        return self._retrieve_alarm_history(query)

    def record_alarm_change(self, alarm_change):
        """Record alarm change event."""
        session = self._engine_facade.get_session()
        with session.begin():
            alarm_change_row = models.AlarmChange(
                event_id=alarm_change['event_id'])
            alarm_change_row.update(alarm_change)
            session.add(alarm_change_row)

    def clear_expired_alarm_history_data(self, alarm_history_ttl):
        """Clear expired alarm history data from the backend storage system.

        Clearing occurs according to the time-to-live.

        :param alarm_history_ttl: Number of seconds to keep alarm history
                                  records for.
        """
        session = self._engine_facade.get_session()
        with session.begin():
            valid_start = (timeutils.utcnow() -
                           datetime.timedelta(seconds=alarm_history_ttl))
            deleted_rows = (session.query(models.AlarmChange)
                            .filter(models.AlarmChange.timestamp < valid_start)
                            .delete())
            LOG.info(_LI("%d alarm histories are removed from database"),
                     deleted_rows)
