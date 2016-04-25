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

import six

from ceilometer import utils


class EventFilter(object):
    """Properties for building an Event query.

    :param start_timestamp: UTC start datetime (mandatory)
    :param end_timestamp: UTC end datetime (mandatory)
    :param event_type: the name of the event. None for all.
    :param message_id: the message_id of the event. None for all.
    :param admin_proj: the project_id of admin role. None if non-admin user.
    :param traits_filter: the trait filter dicts, all of which are optional.
      This parameter is a list of dictionaries that specify trait values:

    .. code-block:: python

        {'key': <key>,
        'string': <value>,
        'integer': <value>,
        'datetime': <value>,
        'float': <value>,
        'op': <eq, lt, le, ne, gt or ge> }
    """

    def __init__(self, start_timestamp=None, end_timestamp=None,
                 event_type=None, message_id=None, traits_filter=None,
                 admin_proj=None):
        self.start_timestamp = utils.sanitize_timestamp(start_timestamp)
        self.end_timestamp = utils.sanitize_timestamp(end_timestamp)
        self.message_id = message_id
        self.event_type = event_type
        self.traits_filter = traits_filter or []
        self.admin_proj = admin_proj

    def __repr__(self):
        return ("<EventFilter(start_timestamp: %s,"
                " end_timestamp: %s,"
                " event_type: %s,"
                " traits: %s)>" %
                (self.start_timestamp,
                 self.end_timestamp,
                 self.event_type,
                 six.text_type(self.traits_filter)))
