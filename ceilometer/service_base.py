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

from oslo_config import cfg
from oslo_log import log
from oslo_service import service as os_service
import six

from ceilometer.i18n import _LE, _LI
from ceilometer import pipeline

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class BaseService(os_service.Service):

    def clear_pipeline_validation_status(self):
        """Clears pipeline validation status flags."""
        self.pipeline_validated = False
        self.event_pipeline_validated = False

    def init_pipeline_refresh(self):
        """Initializes pipeline refresh state."""

        self.clear_pipeline_validation_status()
        if cfg.CONF.refresh_pipeline_cfg:
            self.set_pipeline_mtime(pipeline.get_pipeline_mtime())
            self.set_pipeline_hash(pipeline.get_pipeline_hash())

        if cfg.CONF.refresh_event_pipeline_cfg:
            self.set_pipeline_mtime(pipeline.get_pipeline_mtime(
                pipeline.EVENT_TYPE), pipeline.EVENT_TYPE)
            self.set_pipeline_hash(pipeline.get_pipeline_hash(
                pipeline.EVENT_TYPE), pipeline.EVENT_TYPE)

        if (cfg.CONF.refresh_pipeline_cfg or
                cfg.CONF.refresh_event_pipeline_cfg):
            self.tg.add_timer(cfg.CONF.pipeline_polling_interval,
                              self.refresh_pipeline)

    def get_pipeline_mtime(self, p_type=pipeline.SAMPLE_TYPE):
        return (self.event_pipeline_mtime if p_type == pipeline.EVENT_TYPE else
                self.pipeline_mtime)

    def set_pipeline_mtime(self, mtime, p_type=pipeline.SAMPLE_TYPE):
        if p_type == pipeline.EVENT_TYPE:
            self.event_pipeline_mtime = mtime
        else:
            self.pipeline_mtime = mtime

    def get_pipeline_hash(self, p_type=pipeline.SAMPLE_TYPE):
        return (self.event_pipeline_hash if p_type == pipeline.EVENT_TYPE else
                self.pipeline_hash)

    def set_pipeline_hash(self, _hash, p_type=pipeline.SAMPLE_TYPE):
        if p_type == pipeline.EVENT_TYPE:
            self.event_pipeline_hash = _hash
        else:
            self.pipeline_hash = _hash

    @abc.abstractmethod
    def reload_pipeline(self):
        """Reload pipeline in the agents."""

    def pipeline_changed(self, p_type=pipeline.SAMPLE_TYPE):
        """Returns hash of changed pipeline else False."""

        pipeline_mtime = self.get_pipeline_mtime(p_type)
        mtime = pipeline.get_pipeline_mtime(p_type)
        if mtime > pipeline_mtime:
            LOG.info(_LI('Pipeline configuration file has been updated.'))

            self.set_pipeline_mtime(mtime, p_type)
            _hash = pipeline.get_pipeline_hash(p_type)
            pipeline_hash = self.get_pipeline_hash(p_type)
            if _hash != pipeline_hash:
                LOG.info(_LI("Detected change in pipeline configuration."))
                return _hash
        return False

    def refresh_pipeline(self):
        """Refreshes appropriate pipeline, then delegates to agent."""

        if cfg.CONF.refresh_pipeline_cfg:
            pipeline_hash = self.pipeline_changed()
            if pipeline_hash:
                try:
                    # Pipeline in the notification agent.
                    if hasattr(self, 'pipeline_manager'):
                        self.pipeline_manager = pipeline.setup_pipeline()
                    # Polling in the polling agent.
                    elif hasattr(self, 'polling_manager'):
                        self.polling_manager = pipeline.setup_polling()
                    LOG.debug("Pipeline has been refreshed. "
                              "old hash: %(old)s, new hash: %(new)s",
                              {'old': self.pipeline_hash,
                               'new': pipeline_hash})
                    self.set_pipeline_hash(pipeline_hash)
                    self.pipeline_validated = True
                except Exception as err:
                    LOG.debug("Active pipeline config's hash is %s",
                              self.pipeline_hash)
                    LOG.exception(_LE('Unable to load changed pipeline: %s')
                                  % err)

        if cfg.CONF.refresh_event_pipeline_cfg:
            ev_pipeline_hash = self.pipeline_changed(pipeline.EVENT_TYPE)
            if ev_pipeline_hash:
                try:
                    # Pipeline in the notification agent.
                    if hasattr(self, 'event_pipeline_manager'):
                        self.event_pipeline_manager = (pipeline.
                                                       setup_event_pipeline())

                    LOG.debug("Event Pipeline has been refreshed. "
                              "old hash: %(old)s, new hash: %(new)s",
                              {'old': self.event_pipeline_hash,
                               'new': ev_pipeline_hash})
                    self.set_pipeline_hash(ev_pipeline_hash,
                                           pipeline.EVENT_TYPE)
                    self.event_pipeline_validated = True
                except Exception as err:
                    LOG.debug("Active event pipeline config's hash is %s",
                              self.event_pipeline_hash)
                    LOG.exception(_LE('Unable to load changed event pipeline:'
                                      ' %s') % err)

        if self.pipeline_validated or self.event_pipeline_validated:
            self.reload_pipeline()
            self.clear_pipeline_validation_status()
