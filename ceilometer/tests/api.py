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
import urllib

import flask

from ceilometer.tests import db as db_test_base
from ceilometer.api.v1 import blueprint as v1_blueprint
from ceilometer.api.v1 import app as v1_app


class TestBase(db_test_base.TestBase):

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
