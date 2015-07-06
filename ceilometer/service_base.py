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

from ceilometer.i18n import _, _LE, _LI
from ceilometer import pipeline

LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class BaseService(os_service.Service):

    def init_pipeline_refresh(self):
        if cfg.CONF.refresh_pipeline_cfg:

            self.pipeline_mtime = pipeline.get_pipeline_mtime()
            self.pipeline_hash = pipeline.get_pipeline_hash()

            self.tg.add_timer(cfg.CONF.pipeline_polling_interval,
                              self.refresh_pipeline)

    @abc.abstractmethod
    def reload_pipeline(self):
        """Reload pipeline in the agents."""

    def refresh_pipeline(self):
        mtime = pipeline.get_pipeline_mtime()
        if mtime > self.pipeline_mtime:
            LOG.info(_LI('Pipeline configuration file has been updated.'))

            self.pipeline_mtime = mtime
            _hash = pipeline.get_pipeline_hash()

            if _hash != self.pipeline_hash:
                LOG.info(_LI("Detected change in pipeline configuration."))

                try:
                    # Pipeline in the notification agent.
                    if hasattr(self, 'pipeline_manager'):
                        self.pipeline_manager = pipeline.setup_pipeline()
                    # Polling in the polling agent.
                    elif hasattr(self, 'polling_manager'):
                        self.polling_manager = pipeline.setup_polling()
                    LOG.debug(_("Pipeline has been refreshed. "
                                "old hash: %(old)s, new hash: %(new)s") %
                              ({'old': self.pipeline_hash,
                                'new': _hash}))
                except Exception as err:
                    LOG.debug(_("Active pipeline config's hash is %s") %
                              self.pipeline_hash)
                    LOG.exception(_LE('Unable to load changed pipeline: %s')
                                  % err)
                    return

                self.pipeline_hash = _hash
                self.reload_pipeline()
