# -*- encoding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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
"""Handler for producing image counter messages from glance notification
   events.
"""

from ceilometer import counter
from ceilometer import plugin


class ImageBase(plugin.NotificationBase):
    """
    Listen for image.send notifications in order to mediate with
    the metering framework.
    """

    @staticmethod
    def get_event_types():
        return ['image.send']

    def _counter(self, message, name, user_id, project_id):
        metadata = self.notification_to_metadata(message)
        return counter.Counter(
                source='?',
                name=name,
                type='absolute',
                volume=message['payload']['bytes_sent'],
                resource_id=message['payload']['image_id'],
                user_id=user_id,
                project_id=project_id,
                timestamp=message['timestamp'],
                duration=0,
                resource_metadata=metadata,
                )


class ImageDownload(ImageBase):
    """ Emit image_download counter when an image is downloaded. """

    metadata_keys = ['destination_ip', 'owner_id']

    def process_notification(self, message):
        return [
            self._counter(message,
                          'image_download',
                          message['payload']['receiver_user_id'],
                          message['payload']['receiver_tenant_id']),
            ]


class ImageServe(ImageBase):
    """ Emit image_serve counter when an image is served out. """

    metadata_keys = ['destination_ip', 'receiver_user_id',
                     'receiver_tenant_id']

    def process_notification(self, message):
        return [
            self._counter(message,
                          'image_serve',
                          message['payload']['owner_id'],
                          None),
            ]
