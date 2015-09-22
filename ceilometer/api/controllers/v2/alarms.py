#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 IBM Corp.
# Copyright 2013 eNovance <licensing@enovance.com>
# Copyright Ericsson AB 2013. All rights reserved
# Copyright 2014 Hewlett-Packard Company
# Copyright 2015 Huawei Technologies Co., Ltd.
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

import datetime
import itertools
import json
import uuid

import croniter
from oslo_config import cfg
from oslo_context import context
from oslo_log import log
from oslo_utils import netutils
from oslo_utils import timeutils
import pecan
from pecan import rest
import pytz
import six
from six.moves.urllib import parse as urlparse
from stevedore import extension
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

import ceilometer
from ceilometer import alarm as ceilometer_alarm
from ceilometer.alarm.storage import models as alarm_models
from ceilometer.api.controllers.v2.alarm_rules import combination
from ceilometer.api.controllers.v2 import base
from ceilometer.api.controllers.v2 import utils as v2_utils
from ceilometer.api import rbac
from ceilometer.i18n import _
from ceilometer import keystone_client
from ceilometer import messaging
from ceilometer import utils

LOG = log.getLogger(__name__)


ALARM_API_OPTS = [
    cfg.BoolOpt('record_history',
                default=True,
                deprecated_for_removal=True,
                help='Record alarm change events.'
                ),
    cfg.IntOpt('user_alarm_quota',
               default=None,
               deprecated_for_removal=True,
               help='Maximum number of alarms defined for a user.'
               ),
    cfg.IntOpt('project_alarm_quota',
               default=None,
               deprecated_for_removal=True,
               help='Maximum number of alarms defined for a project.'
               ),
    cfg.IntOpt('alarm_max_actions',
               default=-1,
               deprecated_for_removal=True,
               help='Maximum count of actions for each state of an alarm, '
                    'non-positive number means no limit.'),
]

cfg.CONF.register_opts(ALARM_API_OPTS, group='alarm')

state_kind = ["ok", "alarm", "insufficient data"]
state_kind_enum = wtypes.Enum(str, *state_kind)
severity_kind = ["low", "moderate", "critical"]
severity_kind_enum = wtypes.Enum(str, *severity_kind)


class OverQuota(base.ClientSideError):
    def __init__(self, data):
        d = {
            'u': data.user_id,
            'p': data.project_id
        }
        super(OverQuota, self).__init__(
            _("Alarm quota exceeded for user %(u)s on project %(p)s") % d,
            status_code=403)


def is_over_quota(conn, project_id, user_id):
    """Returns False if an alarm is within the set quotas, True otherwise.

    :param conn: a backend connection object
    :param project_id: the ID of the project setting the alarm
    :param user_id: the ID of the user setting the alarm
    """

    over_quota = False

    # Start by checking for user quota
    user_alarm_quota = cfg.CONF.alarm.user_alarm_quota
    if user_alarm_quota is not None:
        user_alarms = list(conn.get_alarms(user=user_id))
        over_quota = len(user_alarms) >= user_alarm_quota

    # If the user quota isn't reached, we check for the project quota
    if not over_quota:
        project_alarm_quota = cfg.CONF.alarm.project_alarm_quota
        if project_alarm_quota is not None:
            project_alarms = list(conn.get_alarms(project=project_id))
            over_quota = len(project_alarms) >= project_alarm_quota

    return over_quota


class CronType(wtypes.UserType):
    """A user type that represents a cron format."""
    basetype = six.string_types
    name = 'cron'

    @staticmethod
    def validate(value):
        # raises ValueError if invalid
        croniter.croniter(value)
        return value


class AlarmTimeConstraint(base.Base):
    """Representation of a time constraint on an alarm."""

    name = wsme.wsattr(wtypes.text, mandatory=True)
    "The name of the constraint"

    _description = None  # provide a default

    def get_description(self):
        if not self._description:
            return ('Time constraint at %s lasting for %s seconds'
                    % (self.start, self.duration))
        return self._description

    def set_description(self, value):
        self._description = value

    description = wsme.wsproperty(wtypes.text, get_description,
                                  set_description)
    "The description of the constraint"

    start = wsme.wsattr(CronType(), mandatory=True)
    "Start point of the time constraint, in cron format"

    duration = wsme.wsattr(wtypes.IntegerType(minimum=0), mandatory=True)
    "How long the constraint should last, in seconds"

    timezone = wsme.wsattr(wtypes.text, default="")
    "Timezone of the constraint"

    def as_dict(self):
        return self.as_dict_from_keys(['name', 'description', 'start',
                                       'duration', 'timezone'])

    @staticmethod
    def validate(tc):
        if tc.timezone:
            try:
                pytz.timezone(tc.timezone)
            except Exception:
                raise base.ClientSideError(_("Timezone %s is not valid")
                                           % tc.timezone)
        return tc

    @classmethod
    def sample(cls):
        return cls(name='SampleConstraint',
                   description='nightly build every night at 23h for 3 hours',
                   start='0 23 * * *',
                   duration=10800,
                   timezone='Europe/Ljubljana')


ALARMS_RULES = extension.ExtensionManager("ceilometer.alarm.rule")
LOG.debug("alarm rules plugin loaded: %s" % ",".join(ALARMS_RULES.names()))


class Alarm(base.Base):
    """Representation of an alarm.

    .. note::
        combination_rule and threshold_rule are mutually exclusive. The *type*
        of the alarm should be set to *threshold* or *combination* and the
        appropriate rule should be filled.
    """

    alarm_id = wtypes.text
    "The UUID of the alarm"

    name = wsme.wsattr(wtypes.text, mandatory=True)
    "The name for the alarm"

    _description = None  # provide a default

    def get_description(self):
        rule = getattr(self, '%s_rule' % self.type, None)
        if not self._description:
            if hasattr(rule, 'default_description'):
                return six.text_type(rule.default_description)
            return "%s alarm rule" % self.type
        return self._description

    def set_description(self, value):
        self._description = value

    description = wsme.wsproperty(wtypes.text, get_description,
                                  set_description)
    "The description of the alarm"

    enabled = wsme.wsattr(bool, default=True)
    "This alarm is enabled?"

    ok_actions = wsme.wsattr([wtypes.text], default=[])
    "The actions to do when alarm state change to ok"

    alarm_actions = wsme.wsattr([wtypes.text], default=[])
    "The actions to do when alarm state change to alarm"

    insufficient_data_actions = wsme.wsattr([wtypes.text], default=[])
    "The actions to do when alarm state change to insufficient data"

    repeat_actions = wsme.wsattr(bool, default=False)
    "The actions should be re-triggered on each evaluation cycle"

    type = base.AdvEnum('type', str, *ALARMS_RULES.names(),
                        mandatory=True)
    "Explicit type specifier to select which rule to follow below."

    time_constraints = wtypes.wsattr([AlarmTimeConstraint], default=[])
    """Describe time constraints for the alarm"""

    # These settings are ignored in the PUT or POST operations, but are
    # filled in for GET
    project_id = wtypes.text
    "The ID of the project or tenant that owns the alarm"

    user_id = wtypes.text
    "The ID of the user who created the alarm"

    timestamp = datetime.datetime
    "The date of the last alarm definition update"

    state = base.AdvEnum('state', str, *state_kind,
                         default='insufficient data')
    "The state offset the alarm"

    state_timestamp = datetime.datetime
    "The date of the last alarm state changed"

    severity = base.AdvEnum('severity', str, *severity_kind,
                            default='low')
    "The severity of the alarm"

    def __init__(self, rule=None, time_constraints=None, **kwargs):
        super(Alarm, self).__init__(**kwargs)

        if rule:
            setattr(self, '%s_rule' % self.type,
                    ALARMS_RULES[self.type].plugin(**rule))

        if time_constraints:
            self.time_constraints = [AlarmTimeConstraint(**tc)
                                     for tc in time_constraints]

    @staticmethod
    def validate(alarm):

        Alarm.check_rule(alarm)
        Alarm.check_alarm_actions(alarm)

        ALARMS_RULES[alarm.type].plugin.validate_alarm(alarm)

        if alarm.time_constraints:
            tc_names = [tc.name for tc in alarm.time_constraints]
            if len(tc_names) > len(set(tc_names)):
                error = _("Time constraint names must be "
                          "unique for a given alarm.")
                raise base.ClientSideError(error)

        return alarm

    @staticmethod
    def check_rule(alarm):
        rule = '%s_rule' % alarm.type
        if getattr(alarm, rule) in (wtypes.Unset, None):
            error = _("%(rule)s must be set for %(type)s"
                      " type alarm") % {"rule": rule, "type": alarm.type}
            raise base.ClientSideError(error)

        rule_set = None
        for ext in ALARMS_RULES:
            name = "%s_rule" % ext.name
            if getattr(alarm, name):
                if rule_set is None:
                    rule_set = name
                else:
                    error = _("%(rule1)s and %(rule2)s cannot be set at the "
                              "same time") % {'rule1': rule_set, 'rule2': name}
                    raise base.ClientSideError(error)

    @staticmethod
    def check_alarm_actions(alarm):
        actions_schema = ceilometer_alarm.NOTIFIER_SCHEMAS
        max_actions = cfg.CONF.alarm.alarm_max_actions
        for state in state_kind:
            actions_name = state.replace(" ", "_") + '_actions'
            actions = getattr(alarm, actions_name)
            if not actions:
                continue

            action_set = set(actions)
            if len(actions) != len(action_set):
                LOG.info(_('duplicate actions are found: %s, '
                           'remove duplicate ones') % actions)
                actions = list(action_set)
                setattr(alarm, actions_name, actions)

            if 0 < max_actions < len(actions):
                error = _('%(name)s count exceeds maximum value '
                          '%(maximum)d') % {"name": actions_name,
                                            "maximum": max_actions}
                raise base.ClientSideError(error)

            limited = rbac.get_limited_to_project(pecan.request.headers)

            for action in actions:
                try:
                    url = netutils.urlsplit(action)
                except Exception:
                    error = _("Unable to parse action %s") % action
                    raise base.ClientSideError(error)
                if url.scheme not in actions_schema:
                    error = _("Unsupported action %s") % action
                    raise base.ClientSideError(error)
                if limited and url.scheme in ('log', 'test'):
                    error = _('You are not authorized to create '
                              'action: %s') % action
                    raise base.ClientSideError(error, status_code=401)

    @classmethod
    def sample(cls):
        return cls(alarm_id=None,
                   name="SwiftObjectAlarm",
                   description="An alarm",
                   type='combination',
                   time_constraints=[AlarmTimeConstraint.sample().as_dict()],
                   user_id="c96c887c216949acbdfbd8b494863567",
                   project_id="c96c887c216949acbdfbd8b494863567",
                   enabled=True,
                   timestamp=datetime.datetime.utcnow(),
                   state="ok",
                   severity="moderate",
                   state_timestamp=datetime.datetime.utcnow(),
                   ok_actions=["http://site:8000/ok"],
                   alarm_actions=["http://site:8000/alarm"],
                   insufficient_data_actions=["http://site:8000/nodata"],
                   repeat_actions=False,
                   combination_rule=combination.AlarmCombinationRule.sample(),
                   )

    def as_dict(self, db_model):
        d = super(Alarm, self).as_dict(db_model)
        for k in d:
            if k.endswith('_rule'):
                del d[k]
        d['rule'] = getattr(self, "%s_rule" % self.type).as_dict()
        if self.time_constraints:
            d['time_constraints'] = [tc.as_dict()
                                     for tc in self.time_constraints]
        return d

    @staticmethod
    def _is_trust_url(url):
        return url.scheme in ('trust+http', 'trust+https')

    def update_actions(self, old_alarm=None):
        trustor_user_id = pecan.request.headers.get('X-User-Id')
        trustor_project_id = pecan.request.headers.get('X-Project-Id')
        roles = pecan.request.headers.get('X-Roles', '')
        if roles:
            roles = roles.split(',')
        else:
            roles = []
        auth_plugin = pecan.request.environ.get('keystone.token_auth')
        for actions in (self.ok_actions, self.alarm_actions,
                        self.insufficient_data_actions):
            if actions is not None:
                for index, action in enumerate(actions[:]):
                    url = netutils.urlsplit(action)
                    if self._is_trust_url(url):
                        if '@' not in url.netloc:
                            # We have a trust action without a trust ID,
                            # create it
                            trust_id = keystone_client.create_trust_id(
                                trustor_user_id, trustor_project_id, roles,
                                auth_plugin)
                            netloc = '%s:delete@%s' % (trust_id, url.netloc)
                            url = list(url)
                            url[1] = netloc
                            actions[index] = urlparse.urlunsplit(url)
        if old_alarm:
            new_actions = list(itertools.chain(
                self.ok_actions or [],
                self.alarm_actions or [],
                self.insufficient_data_actions or []))
            for action in itertools.chain(
                    old_alarm.ok_actions or [],
                    old_alarm.alarm_actions or [],
                    old_alarm.insufficient_data_actions or []):
                if action not in new_actions:
                    self.delete_trust(action)

    def delete_actions(self):
        for action in itertools.chain(self.ok_actions or [],
                                      self.alarm_actions or [],
                                      self.insufficient_data_actions or []):
            self.delete_trust(action)

    def delete_trust(self, action):
        auth_plugin = pecan.request.environ.get('keystone.token_auth')
        url = netutils.urlsplit(action)
        if self._is_trust_url(url) and url.password:
            keystone_client.delete_trust_id(url.username, auth_plugin)


Alarm.add_attributes(**{"%s_rule" % ext.name: ext.plugin
                        for ext in ALARMS_RULES})


class AlarmChange(base.Base):
    """Representation of an event in an alarm's history."""

    event_id = wtypes.text
    "The UUID of the change event"

    alarm_id = wtypes.text
    "The UUID of the alarm"

    type = wtypes.Enum(str,
                       'creation',
                       'rule change',
                       'state transition',
                       'deletion')
    "The type of change"

    detail = wtypes.text
    "JSON fragment describing change"

    project_id = wtypes.text
    "The project ID of the initiating identity"

    user_id = wtypes.text
    "The user ID of the initiating identity"

    on_behalf_of = wtypes.text
    "The tenant on behalf of which the change is being made"

    timestamp = datetime.datetime
    "The time/date of the alarm change"

    @classmethod
    def sample(cls):
        return cls(alarm_id='e8ff32f772a44a478182c3fe1f7cad6a',
                   type='rule change',
                   detail='{"threshold": 42.0, "evaluation_periods": 4}',
                   user_id="3e5d11fda79448ac99ccefb20be187ca",
                   project_id="b6f16144010811e387e4de429e99ee8c",
                   on_behalf_of="92159030020611e3b26dde429e99ee8c",
                   timestamp=datetime.datetime.utcnow(),
                   )


def _send_notification(event, payload):
    notification = event.replace(" ", "_")
    notification = "alarm.%s" % notification
    transport = messaging.get_transport()
    notifier = messaging.get_notifier(transport, publisher_id="ceilometer.api")
    # FIXME(sileht): perhaps we need to copy some infos from the
    # pecan request headers like nova does
    notifier.info(context.RequestContext(), notification, payload)


class AlarmController(rest.RestController):
    """Manages operations on a single alarm."""

    _custom_actions = {
        'history': ['GET'],
        'state': ['PUT', 'GET'],
    }

    def __init__(self, alarm_id):
        pecan.request.context['alarm_id'] = alarm_id
        self._id = alarm_id

    def _alarm(self):
        self.conn = pecan.request.alarm_storage_conn
        auth_project = rbac.get_limited_to_project(pecan.request.headers)
        alarms = list(self.conn.get_alarms(alarm_id=self._id,
                                           project=auth_project))
        if not alarms:
            raise base.AlarmNotFound(alarm=self._id, auth_project=auth_project)
        return alarms[0]

    def _record_change(self, data, now, on_behalf_of=None, type=None):
        if not cfg.CONF.alarm.record_history:
            return
        if not data:
            return
        type = type or alarm_models.AlarmChange.RULE_CHANGE
        scrubbed_data = utils.stringify_timestamps(data)
        detail = json.dumps(scrubbed_data)
        user_id = pecan.request.headers.get('X-User-Id')
        project_id = pecan.request.headers.get('X-Project-Id')
        on_behalf_of = on_behalf_of or project_id
        payload = dict(event_id=str(uuid.uuid4()),
                       alarm_id=self._id,
                       type=type,
                       detail=detail,
                       user_id=user_id,
                       project_id=project_id,
                       on_behalf_of=on_behalf_of,
                       timestamp=now)

        try:
            self.conn.record_alarm_change(payload)
        except ceilometer.NotImplementedError:
            pass

        # Revert to the pre-json'ed details ...
        payload['detail'] = scrubbed_data
        _send_notification(type, payload)

    @wsme_pecan.wsexpose(Alarm)
    def get(self):
        """Return this alarm."""

        rbac.enforce('get_alarm', pecan.request)

        return Alarm.from_db_model(self._alarm())

    @wsme_pecan.wsexpose(Alarm, body=Alarm)
    def put(self, data):
        """Modify this alarm.

        :param data: an alarm within the request body.
        """

        rbac.enforce('change_alarm', pecan.request)

        # Ensure alarm exists
        alarm_in = self._alarm()

        now = timeutils.utcnow()

        data.alarm_id = self._id

        user, project = rbac.get_limited_to(pecan.request.headers)
        if user:
            data.user_id = user
        elif data.user_id == wtypes.Unset:
            data.user_id = alarm_in.user_id
        if project:
            data.project_id = project
        elif data.project_id == wtypes.Unset:
            data.project_id = alarm_in.project_id
        data.timestamp = now
        if alarm_in.state != data.state:
            data.state_timestamp = now
        else:
            data.state_timestamp = alarm_in.state_timestamp

        # make sure alarms are unique by name per project.
        if alarm_in.name != data.name:
            alarms = list(self.conn.get_alarms(name=data.name,
                                               project=data.project_id))
            if alarms:
                raise base.ClientSideError(
                    _("Alarm with name=%s exists") % data.name,
                    status_code=409)

        ALARMS_RULES[data.type].plugin.update_hook(data)

        old_data = Alarm.from_db_model(alarm_in)
        old_alarm = old_data.as_dict(alarm_models.Alarm)
        data.update_actions(old_data)
        updated_alarm = data.as_dict(alarm_models.Alarm)
        try:
            alarm_in = alarm_models.Alarm(**updated_alarm)
        except Exception:
            LOG.exception(_("Error while putting alarm: %s") % updated_alarm)
            raise base.ClientSideError(_("Alarm incorrect"))

        alarm = self.conn.update_alarm(alarm_in)

        change = dict((k, v) for k, v in updated_alarm.items()
                      if v != old_alarm[k] and k not in
                      ['timestamp', 'state_timestamp'])
        self._record_change(change, now, on_behalf_of=alarm.project_id)
        return Alarm.from_db_model(alarm)

    @wsme_pecan.wsexpose(None, status_code=204)
    def delete(self):
        """Delete this alarm."""

        rbac.enforce('delete_alarm', pecan.request)

        # ensure alarm exists before deleting
        alarm = self._alarm()
        self.conn.delete_alarm(alarm.alarm_id)
        alarm_object = Alarm.from_db_model(alarm)
        alarm_object.delete_actions()

    @wsme_pecan.wsexpose([AlarmChange], [base.Query])
    def history(self, q=None):
        """Assembles the alarm history requested.

        :param q: Filter rules for the changes to be described.
        """

        rbac.enforce('alarm_history', pecan.request)

        q = q or []
        # allow history to be returned for deleted alarms, but scope changes
        # returned to those carried out on behalf of the auth'd tenant, to
        # avoid inappropriate cross-tenant visibility of alarm history
        auth_project = rbac.get_limited_to_project(pecan.request.headers)
        conn = pecan.request.alarm_storage_conn
        kwargs = v2_utils.query_to_kwargs(
            q, conn.get_alarm_changes, ['on_behalf_of', 'alarm_id'])
        return [AlarmChange.from_db_model(ac)
                for ac in conn.get_alarm_changes(self._id, auth_project,
                                                 **kwargs)]

    @wsme.validate(state_kind_enum)
    @wsme_pecan.wsexpose(state_kind_enum, body=state_kind_enum)
    def put_state(self, state):
        """Set the state of this alarm.

        :param state: an alarm state within the request body.
        """

        rbac.enforce('change_alarm_state', pecan.request)

        # note(sileht): body are not validated by wsme
        # Workaround for https://bugs.launchpad.net/wsme/+bug/1227229
        if state not in state_kind:
            raise base.ClientSideError(_("state invalid"))
        now = timeutils.utcnow()
        alarm = self._alarm()
        alarm.state = state
        alarm.state_timestamp = now
        alarm = self.conn.update_alarm(alarm)
        change = {'state': alarm.state}
        self._record_change(change, now, on_behalf_of=alarm.project_id,
                            type=alarm_models.AlarmChange.STATE_TRANSITION)
        return alarm.state

    @wsme_pecan.wsexpose(state_kind_enum)
    def get_state(self):
        """Get the state of this alarm."""

        rbac.enforce('get_alarm_state', pecan.request)

        alarm = self._alarm()
        return alarm.state


class AlarmsController(rest.RestController):
    """Manages operations on the alarms collection."""

    @pecan.expose()
    def _lookup(self, alarm_id, *remainder):
        return AlarmController(alarm_id), remainder

    @staticmethod
    def _record_creation(conn, data, alarm_id, now):
        if not cfg.CONF.alarm.record_history:
            return
        type = alarm_models.AlarmChange.CREATION
        scrubbed_data = utils.stringify_timestamps(data)
        detail = json.dumps(scrubbed_data)
        user_id = pecan.request.headers.get('X-User-Id')
        project_id = pecan.request.headers.get('X-Project-Id')
        payload = dict(event_id=str(uuid.uuid4()),
                       alarm_id=alarm_id,
                       type=type,
                       detail=detail,
                       user_id=user_id,
                       project_id=project_id,
                       on_behalf_of=project_id,
                       timestamp=now)

        try:
            conn.record_alarm_change(payload)
        except ceilometer.NotImplementedError:
            pass

        # Revert to the pre-json'ed details ...
        payload['detail'] = scrubbed_data
        _send_notification(type, payload)

    @wsme_pecan.wsexpose(Alarm, body=Alarm, status_code=201)
    def post(self, data):
        """Create a new alarm.

        :param data: an alarm within the request body.
        """
        rbac.enforce('create_alarm', pecan.request)

        conn = pecan.request.alarm_storage_conn
        now = timeutils.utcnow()

        data.alarm_id = str(uuid.uuid4())
        user_limit, project_limit = rbac.get_limited_to(pecan.request.headers)

        def _set_ownership(aspect, owner_limitation, header):
            attr = '%s_id' % aspect
            requested_owner = getattr(data, attr)
            explicit_owner = requested_owner != wtypes.Unset
            caller = pecan.request.headers.get(header)
            if (owner_limitation and explicit_owner
                    and requested_owner != caller):
                raise base.ProjectNotAuthorized(requested_owner, aspect)

            actual_owner = (owner_limitation or
                            requested_owner if explicit_owner else caller)
            setattr(data, attr, actual_owner)

        _set_ownership('user', user_limit, 'X-User-Id')
        _set_ownership('project', project_limit, 'X-Project-Id')

        # Check if there's room for one more alarm
        if is_over_quota(conn, data.project_id, data.user_id):
            raise OverQuota(data)

        data.timestamp = now
        data.state_timestamp = now

        ALARMS_RULES[data.type].plugin.create_hook(data)

        data.update_actions()
        change = data.as_dict(alarm_models.Alarm)

        # make sure alarms are unique by name per project.
        alarms = list(conn.get_alarms(name=data.name,
                                      project=data.project_id))
        if alarms:
            raise base.ClientSideError(
                _("Alarm with name='%s' exists") % data.name,
                status_code=409)

        try:
            alarm_in = alarm_models.Alarm(**change)
        except Exception:
            LOG.exception(_("Error while posting alarm: %s") % change)
            raise base.ClientSideError(_("Alarm incorrect"))

        alarm = conn.create_alarm(alarm_in)
        self._record_creation(conn, change, alarm.alarm_id, now)
        return Alarm.from_db_model(alarm)

    @wsme_pecan.wsexpose([Alarm], [base.Query])
    def get_all(self, q=None):
        """Return all alarms, based on the query provided.

        :param q: Filter rules for the alarms to be returned.
        """

        rbac.enforce('get_alarms', pecan.request)

        q = q or []
        # Timestamp is not supported field for Simple Alarm queries
        kwargs = v2_utils.query_to_kwargs(
            q, pecan.request.alarm_storage_conn.get_alarms,
            allow_timestamps=False)
        return [Alarm.from_db_model(m)
                for m in pecan.request.alarm_storage_conn.get_alarms(**kwargs)]
