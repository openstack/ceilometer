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

from ceilometer import pipeline

LOG = log.getLogger(__name__)


class SampleEndpoint(pipeline.NotificationEndpoint):

    def info(self, notifications):
        """Convert message at info level to Ceilometer sample.

        :param notifications: list of notifications
        """
        return self.process_notifications('info', notifications)

    def sample(self, notifications):
        """Convert message at sample level to Ceilometer Event.

        :param notifications: list of notifications
        """
        return self.process_notifications('sample', notifications)

    def process_notifications(self, priority, notifications):
        for message in notifications:
            try:
                with self.manager.publisher() as p:
                    p(list(self.build_sample(message)))
            except Exception:
                LOG.error('Fail to process notification', exc_info=True)

    def build_sample(notification):
        """Build sample from provided notification."""
        pass
