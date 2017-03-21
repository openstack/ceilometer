#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from oslo_log import log
import oslo_messaging
from oslo_policy import policy

from pecan import hooks

from ceilometer import messaging
from ceilometer import storage

LOG = log.getLogger(__name__)


class ConfigHook(hooks.PecanHook):
    """Attach the configuration object to the request.

    That allows controllers to get it.
    """
    def __init__(self, conf):
        super(ConfigHook, self).__init__()
        self.conf = conf
        self.enforcer = policy.Enforcer(conf)
        self.enforcer.load_rules()

    def on_route(self, state):
        state.request.cfg = self.conf
        state.request.enforcer = self.enforcer


class DBHook(hooks.PecanHook):

    def __init__(self, conf):
        self.storage_connection = self.get_connection(conf)

        if not self.storage_connection:
            raise Exception(
                "API failed to start. Failed to connect to database")

    def before(self, state):
        state.request.storage_conn = self.storage_connection

    @staticmethod
    def get_connection(conf):
        try:
            return storage.get_connection_from_config(conf)
        except Exception as err:
            LOG.exception("Failed to connect to db" "retry later: %s",
                          err)


class NotifierHook(hooks.PecanHook):
    """Create and attach a notifier to the request.

    Usually, samples will be push to notification bus by notifier when they
    are posted via /v2/meters/ API.
    """

    def __init__(self, conf):
        transport = messaging.get_transport(conf)
        self.notifier = oslo_messaging.Notifier(
            transport, driver=conf.publisher_notifier.telemetry_driver,
            publisher_id="ceilometer.api")

    def before(self, state):
        state.request.notifier = self.notifier


class TranslationHook(hooks.PecanHook):

    def after(self, state):
        # After a request has been done, we need to see if
        # ClientSideError has added an error onto the response.
        # If it has we need to get it info the thread-safe WSGI
        # environ to be used by the ParsableErrorMiddleware.
        if hasattr(state.response, 'translatable_error'):
            state.request.environ['translatable_error'] = (
                state.response.translatable_error)
