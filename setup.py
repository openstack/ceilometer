#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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

import setuptools

setuptools.setup(
    name='ceilometer',
    version='0',
    description='cloud computing metering',
    author='OpenStack',
    author_email='ceilometer@lists.launchpad.net',
    url='https://launchpad.net/ceilometer',
    packages=setuptools.find_packages(exclude=['bin']),
    include_package_data=True,
    test_suite='nose.collector',
    scripts=['bin/ceilometer-agent', 'bin/ceilometer-collector'],
    py_modules=[],
    entry_points={
        'ceilometer.collector.compute': [
            'instance_create'
            '= ceilometer.compute.notifications:InstanceCreate',
            ],
        'ceilometer.poll.compute': [
            'libvirt_diskio = ceilometer.compute.libvirt:DiskIOPollster',
            'libvirt_cpu = ceilometer.compute.libvirt:CPUPollster',
            'network_floatingip'
            '= ceilometer.compute.network:FloatingIPPollster',
            ],
        },
    )
