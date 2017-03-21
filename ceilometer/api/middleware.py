#
# Copyright 2013 IBM Corp.
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
"""Middleware to replace the plain text message body of an error
response with one formatted so the client can parse it.

Based on pecan.middleware.errordocument
"""

import json

from lxml import etree
from oslo_log import log
import six
import webob

from ceilometer import i18n

LOG = log.getLogger(__name__)


class ParsableErrorMiddleware(object):
    """Replace error body with something the client can parse."""

    @staticmethod
    def best_match_language(accept_language):
        """Determines best available locale from the Accept-Language header.

        :returns: the best language match or None if the 'Accept-Language'
                  header was not available in the request.
        """
        if not accept_language:
            return None
        all_languages = i18n.get_available_languages()
        return accept_language.best_match(all_languages)

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Request for this state, modified by replace_start_response()
        # and used when an error is being reported.
        state = {}

        def replacement_start_response(status, headers, exc_info=None):
            """Overrides the default response to make errors parsable."""
            try:
                status_code = int(status.split(' ')[0])
                state['status_code'] = status_code
            except (ValueError, TypeError):  # pragma: nocover
                raise Exception((
                    'ErrorDocumentMiddleware received an invalid '
                    'status %s' % status
                ))
            else:
                if (state['status_code'] // 100) not in (2, 3):
                    # Remove some headers so we can replace them later
                    # when we have the full error message and can
                    # compute the length.
                    headers = [(h, v)
                               for (h, v) in headers
                               if h not in ('Content-Length', 'Content-Type')
                               ]
                # Save the headers in case we need to modify them.
                state['headers'] = headers
                return start_response(status, headers, exc_info)

        app_iter = self.app(environ, replacement_start_response)
        if (state['status_code'] // 100) not in (2, 3):
            req = webob.Request(environ)
            error = environ.get('translatable_error')
            user_locale = self.best_match_language(req.accept_language)
            if (req.accept.best_match(['application/json', 'application/xml'])
               == 'application/xml'):
                content_type = 'application/xml'
                try:
                    # simple check xml is valid
                    fault = etree.fromstring(b'\n'.join(app_iter))
                    # Add the translated error to the xml data
                    if error is not None:
                        for fault_string in fault.findall('faultstring'):
                            fault_string.text = i18n.translate(error,
                                                               user_locale)
                    error_message = etree.tostring(fault)
                    body = b''.join((b'<error_message>',
                                     error_message,
                                     b'</error_message>'))
                except etree.XMLSyntaxError as err:
                    LOG.error('Error parsing HTTP response: %s', err)
                    error_message = state['status_code']
                    body = '<error_message>%s</error_message>' % error_message
                    if six.PY3:
                        body = body.encode('utf-8')
            else:
                content_type = 'application/json'
                app_data = b'\n'.join(app_iter)
                if six.PY3:
                    app_data = app_data.decode('utf-8')
                try:
                    fault = json.loads(app_data)
                    if error is not None and 'faultstring' in fault:
                        fault['faultstring'] = i18n.translate(error,
                                                              user_locale)
                except ValueError as err:
                    fault = app_data
                body = json.dumps({'error_message': fault})
                if six.PY3:
                    body = body.encode('utf-8')

            state['headers'].append(('Content-Length', str(len(body))))
            state['headers'].append(('Content-Type', content_type))
            body = [body]
        else:
            body = app_iter
        return body
