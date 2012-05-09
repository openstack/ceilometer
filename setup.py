#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import setuptools

setuptools.setup(name='ceilometer',
                 version='0',
                 description='cloud computing metering',
                 author='OpenStack',
                 author_email='ceilometer@lists.launchpad.net',
                 url='https://launchpad.net/ceilometer',
                 packages=setuptools.find_packages(exclude=['bin']),
                 include_package_data=True,
                 test_suite='nose.collector',
                 scripts=['bin/ceilometer-nova-compute'],
                 py_modules=[])
