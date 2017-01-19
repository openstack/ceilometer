#
# Copyright 2013 eNovance
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

from ceilometer import notification
from ceilometer import sample


class HTTPRequest(notification.NotificationProcessBase):
    event_types = ['http.request']

    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name=message['event_type'],
            type=sample.TYPE_DELTA,
            volume=1,
            unit=message['event_type'].split('.')[1],
            user_id=message['payload']['request'].get('HTTP_X_USER_ID'),
            project_id=message['payload']['request'].get('HTTP_X_PROJECT_ID'),
            resource_id=message['payload']['request'].get(
                'HTTP_X_SERVICE_NAME'),
            message=message)


class HTTPResponse(HTTPRequest):
    event_types = ['http.response']
