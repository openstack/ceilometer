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

import json
import os
import urllib
import unittest

import flask
from pecan import set_config
from pecan.testing import load_test_app

import mox
import stubout

from ceilometer import storage
from ceilometer.api.v1 import app as v1_app
from ceilometer.api.v1 import blueprint as v1_blueprint
from ceilometer.api.controllers import v2
from ceilometer.openstack.common import cfg
from ceilometer.tests import db as db_test_base


class TestBase(db_test_base.TestBase):
    """Use only for v1 API tests.
    """

    def setUp(self):
        super(TestBase, self).setUp()
        self.app = v1_app.make_app(enable_acl=False, attach_storage=False)
        self.app.register_blueprint(v1_blueprint.blueprint)
        self.test_app = self.app.test_client()

        @self.app.before_request
        def attach_storage_connection():
            flask.request.storage_conn = self.conn

    def get(self, path, **kwds):
        if kwds:
            query = path + '?' + urllib.urlencode(kwds)
        else:
            query = path
        rv = self.test_app.get(query)
        try:
            data = json.loads(rv.data)
        except ValueError:
            print 'RAW DATA:', rv
            raise
        return data


class FunctionalTest(unittest.TestCase):
    """
    Used for functional tests of Pecan controllers where you need to
    test your literal application and its integration with the
    framework.
    """

    DBNAME = 'testdb'

    PATH_PREFIX = ''

    SOURCE_DATA = {'test_source': {'somekey': '666'}}

    def setUp(self):

        cfg.CONF.database_connection = 'test://localhost/%s' % self.DBNAME
        self.conn = storage.get_connection(cfg.CONF)
        # Don't want to use drop_database() because we
        # may end up running out of spidermonkey instances.
        # http://davisp.lighthouseapp.com/projects/26898/tickets/22
        self.conn.conn[self.DBNAME].clear()

        # Determine where we are so we can set up paths in the config
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..',
                                                '..',
                                                )
                                   )
        self.config = {

            'app': {
                'root': 'ceilometer.api.controllers.root.RootController',
                'modules': ['ceilometer.api'],
                'static_root': '%s/public' % root_dir,
                'template_path': '%s/ceilometer/api/templates' % root_dir,
                },

            'logging': {
                'loggers': {
                    'root': {'level': 'INFO', 'handlers': ['console']},
                    'ceilometer': {'level': 'DEBUG',
                                   'handlers': ['console'],
                                   },
                    },
                'handlers': {
                    'console': {
                        'level': 'DEBUG',
                        'class': 'logging.StreamHandler',
                        'formatter': 'simple'
                        }
                    },
                'formatters': {
                    'simple': {
                        'format': ('%(asctime)s %(levelname)-5.5s [%(name)s]'
                                   '[%(threadName)s] %(message)s')
                        }
                    },
                },
            }

        self.mox = mox.Mox()
        self.stubs = stubout.StubOutForTesting()

        self.app = self._make_app()
        self._stubout_sources()

    def _make_app(self):
        return load_test_app(self.config)

    def _stubout_sources(self):
        """Source data is usually read from a file, but
        we want to let tests define their own. The class
        attribute SOURCE_DATA is injected into the controller
        as though it was read from the usual configuration
        file.
        """
        self.stubs.SmartSet(v2.SourcesController, 'sources',
                            self.SOURCE_DATA)

    def tearDown(self):
        self.mox.UnsetStubs()
        self.stubs.UnsetAll()
        self.stubs.SmartUnsetAll()
        self.mox.VerifyAll()
        set_config({}, overwrite=True)

    def get_json(self, path, expect_errors=False, headers=None, **params):
        full_path = self.PATH_PREFIX + path
        print 'GET: %s %r' % (full_path, params)
        response = self.app.get(full_path,
                                params=params,
                                headers=headers,
                                expect_errors=expect_errors)
        if not expect_errors:
            response = response.json
        print 'GOT:', response
        return response
