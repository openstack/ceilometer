# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Base classes for API tests.
"""

import urllib

import flask
import pecan
import pecan.testing

from ceilometer.api import acl
from ceilometer.api.v1 import app as v1_app
from ceilometer.api.v1 import blueprint as v1_blueprint
from ceilometer.openstack.common import jsonutils
from ceilometer import service
from ceilometer.tests import db as db_test_base


class TestBase(db_test_base.TestBase):
    """Use only for v1 API tests.
    """

    def setUp(self):
        super(TestBase, self).setUp()
        service.prepare_service([])
        self.CONF.set_override("auth_version",
                               "v2.0", group=acl.OPT_GROUP_NAME)
        self.CONF.set_override("policy_file",
                               self.path_get('etc/ceilometer/policy.json'))
        sources_file = self.path_get('ceilometer/tests/sources.json')
        self.app = v1_app.make_app(self.CONF,
                                   enable_acl=False,
                                   attach_storage=False,
                                   sources_file=sources_file)

        # this is needed to pass over unhandled exceptions
        self.app.debug = True

        self.app.register_blueprint(v1_blueprint.blueprint)
        self.test_app = self.app.test_client()

        @self.app.before_request
        def attach_storage_connection():
            flask.request.storage_conn = self.conn

    def get(self, path, headers=None, **kwds):
        if kwds:
            query = path + '?' + urllib.urlencode(kwds)
        else:
            query = path
        rv = self.test_app.get(query, headers=headers)
        if rv.status_code == 200 and rv.content_type == 'application/json':
            try:
                data = jsonutils.loads(rv.data)
            except ValueError:
                print('RAW DATA:%s' % rv)
                raise
            return data
        return rv


class FunctionalTest(db_test_base.TestBase):
    """Used for functional tests of Pecan controllers where you need to
    test your literal application and its integration with the
    framework.
    """

    PATH_PREFIX = ''

    def setUp(self):
        super(FunctionalTest, self).setUp()
        self.CONF.set_override("auth_version", "v2.0",
                               group=acl.OPT_GROUP_NAME)
        self.CONF.set_override("policy_file",
                               self.path_get('etc/ceilometer/policy.json'))
        self.app = self._make_app()

    def _make_app(self, enable_acl=False):
        # Determine where we are so we can set up paths in the config
        root_dir = self.path_get()

        self.config = {
            'app': {
                'root': 'ceilometer.api.controllers.root.RootController',
                'modules': ['ceilometer.api'],
                'static_root': '%s/public' % root_dir,
                'template_path': '%s/ceilometer/api/templates' % root_dir,
                'enable_acl': enable_acl,
            },
            'wsme': {
                'debug': True,
            },
        }

        return pecan.testing.load_test_app(self.config)

    def tearDown(self):
        super(FunctionalTest, self).tearDown()
        pecan.set_config({}, overwrite=True)

    def put_json(self, path, params, expect_errors=False, headers=None,
                 extra_environ=None, status=None):
        """Sends simulated HTTP PUT request to Pecan test app.

        :param path: url path of target service
        :param params: content for wsgi.input of request
        :param expect_errors: boolean value whether an error is expected based
                              on request
        :param headers: A dictionary of headers to send along with the request
        :param extra_environ: A dictionary of environ variables to send along
                              with the request
        :param status: Expected status code of response
        """
        return self.post_json(path=path, params=params,
                              expect_errors=expect_errors,
                              headers=headers, extra_environ=extra_environ,
                              status=status, method="put")

    def post_json(self, path, params, expect_errors=False, headers=None,
                  method="post", extra_environ=None, status=None):
        """Sends simulated HTTP POST request to Pecan test app.

        :param path: url path of target service
        :param params: content for wsgi.input of request
        :param expect_errors: boolean value whether an error is expected based
                              on request
        :param headers: A dictionary of headers to send along with the request
        :param method: Request method type. Appropriate method function call
                       should be used rather than passing attribute in.
        :param extra_environ: A dictionary of environ variables to send along
                              with the request
        :param status: Expected status code of response
        """
        full_path = self.PATH_PREFIX + path
        response = getattr(self.app, "%s_json" % method)(
            str(full_path),
            params=params,
            headers=headers,
            status=status,
            extra_environ=extra_environ,
            expect_errors=expect_errors
        )
        return response

    def delete(self, path, expect_errors=False, headers=None,
               extra_environ=None, status=None):
        """Sends simulated HTTP DELETE request to Pecan test app.

        :param path: url path of target service
        :param expect_errors: boolean value whether an error is expected based
                              on request
        :param headers: A dictionary of headers to send along with the request
        :param extra_environ: A dictionary of environ variables to send along
                              with the request
        :param status: Expected status code of response
        """
        full_path = self.PATH_PREFIX + path
        response = self.app.delete(str(full_path),
                                   headers=headers,
                                   status=status,
                                   extra_environ=extra_environ,
                                   expect_errors=expect_errors)
        return response

    def get_json(self, path, expect_errors=False, headers=None,
                 extra_environ=None, q=[], groupby=[], status=None,
                 **params):
        """Sends simulated HTTP GET request to Pecan test app.

        :param path: url path of target service
        :param expect_errors: boolean value whether an error is expected based
                              on request
        :param headers: A dictionary of headers to send along with the request
        :param extra_environ: A dictionary of environ variables to send along
                              with the request
        :param q: list of queries consisting of: field, value, op, and type
                  keys
        :param groupby: list of fields to group by
        :param status: Expected status code of response
        :param params: content for wsgi.input of request
        """
        full_path = self.PATH_PREFIX + path
        query_params = {'q.field': [],
                        'q.value': [],
                        'q.op': [],
                        'q.type': [],
                        }
        for query in q:
            for name in ['field', 'op', 'value', 'type']:
                query_params['q.%s' % name].append(query.get(name, ''))
        all_params = {}
        all_params.update(params)
        if q:
            all_params.update(query_params)
        if groupby:
            all_params.update({'groupby': groupby})
        response = self.app.get(full_path,
                                params=all_params,
                                headers=headers,
                                extra_environ=extra_environ,
                                expect_errors=expect_errors,
                                status=status)
        if not expect_errors:
            response = response.json
        return response
