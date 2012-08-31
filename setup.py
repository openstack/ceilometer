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

import textwrap

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
    setup_requires=['setuptools-git>=0.4'],
    scripts=['bin/ceilometer-agent-compute',
             'bin/ceilometer-agent-central',
             'bin/ceilometer-api',
             'bin/ceilometer-collector'],
    py_modules=[],
    entry_points=textwrap.dedent("""
    [ceilometer.collector.compute]
    instance = ceilometer.compute.notifications:Instance
    instance_flavor = ceilometer.compute.notifications:InstanceFlavor
    memory = ceilometer.compute.notifications:Memory
    vcpus = ceilometer.compute.notifications:VCpus
    root_disk_size = ceilometer.compute.notifications:RootDiskSize
    ephemeral_disk_size = ceilometer.compute.notifications:EphemeralDiskSize

    [ceilometer.poll.compute]
    libvirt_diskio = ceilometer.compute.libvirt:DiskIOPollster
    libvirt_cpu = ceilometer.compute.libvirt:CPUPollster
    libvirt_net = ceilometer.compute.libvirt:NetPollster

    [ceilometer.poll.central]
    network_floatingip = ceilometer.network.floatingip:FloatingIPPollster

    [ceilometer.storage]
    log = ceilometer.storage.impl_log:LogStorage
    mongodb = ceilometer.storage.impl_mongodb:MongoDBStorage
    mysql = ceilometer.storage.impl_sqlalchemy:SQLAlchemyStorage
    postgresql = ceilometer.storage.impl_sqlalchemy:SQLAlchemyStorage
    sqlite = ceilometer.storage.impl_sqlalchemy:SQLAlchemyStorage
    """),
    )
