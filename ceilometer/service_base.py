#
# Copyright 2015 Hewlett Packard
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

import abc

import cotyledon
from oslo_log import log
import six

from ceilometer.i18n import _LE
from ceilometer import pipeline
from ceilometer import utils

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class PipelineBasedService(cotyledon.Service):
    def __init__(self, worker_id, conf):
        super(PipelineBasedService, self).__init__(worker_id)
        self.conf = conf
        self.refresh_pipeline_periodic = None

    def clear_pipeline_validation_status(self):
        """Clears pipeline validation status flags."""
        self.pipeline_validated = False
        self.event_pipeline_validated = False

    def init_pipeline_refresh(self):
        """Initializes pipeline refresh state."""
        self.clear_pipeline_validation_status()

        if (self.conf.refresh_pipeline_cfg or
                self.conf.refresh_event_pipeline_cfg):
            self.refresh_pipeline_periodic = utils.create_periodic(
                target=self.refresh_pipeline,
                spacing=self.conf.pipeline_polling_interval)
            utils.spawn_thread(self.refresh_pipeline_periodic.start)

    def terminate(self):
        if self.refresh_pipeline_periodic:
            self.refresh_pipeline_periodic.stop()
            self.refresh_pipeline_periodic.wait()

    @abc.abstractmethod
    def reload_pipeline(self):
        """Reload pipeline in the agents."""

    def refresh_pipeline(self):
        """Refreshes appropriate pipeline, then delegates to agent."""

        if self.conf.refresh_pipeline_cfg:
            manager = None
            if hasattr(self, 'pipeline_manager'):
                manager = self.pipeline_manager
            elif hasattr(self, 'polling_manager'):
                manager = self.polling_manager
            pipeline_hash = manager.cfg_changed() if manager else None
            if pipeline_hash:
                try:
                    LOG.debug("Pipeline has been refreshed. "
                              "old hash: %(old)s, new hash: %(new)s",
                              {'old': manager.cfg_hash,
                               'new': pipeline_hash})
                    # Pipeline in the notification agent.
                    if hasattr(self, 'pipeline_manager'):
                        self.pipeline_manager = pipeline.setup_pipeline(
                            self.conf)
                    # Polling in the polling agent.
                    elif hasattr(self, 'polling_manager'):
                        self.polling_manager = pipeline.setup_polling(
                            self.conf)
                    self.pipeline_validated = True
                except Exception as err:
                    LOG.exception(_LE('Unable to load changed pipeline: %s')
                                  % err)

        if self.conf.refresh_event_pipeline_cfg:
            # Pipeline in the notification agent.
            manager = (self.event_pipeline_manager
                       if hasattr(self, 'event_pipeline_manager') else None)
            ev_pipeline_hash = manager.cfg_changed()
            if ev_pipeline_hash:
                try:
                    LOG.debug("Event Pipeline has been refreshed. "
                              "old hash: %(old)s, new hash: %(new)s",
                              {'old': manager.cfg_hash,
                               'new': ev_pipeline_hash})
                    self.event_pipeline_manager = (
                        pipeline. setup_event_pipeline(self.conf))
                    self.event_pipeline_validated = True
                except Exception as err:
                    LOG.exception(_LE('Unable to load changed event pipeline:'
                                      ' %s') % err)

        if self.pipeline_validated or self.event_pipeline_validated:
            self.reload_pipeline()
            self.clear_pipeline_validation_status()
