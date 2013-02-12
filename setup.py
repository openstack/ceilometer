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
import os
import setuptools

from ceilometer.openstack.common import setup as common_setup

requires = common_setup.parse_requirements(['tools/pip-requires'])
depend_links = common_setup.parse_dependency_links(['tools/pip-requires'])
project = 'ceilometer'
version = common_setup.get_version(project, '2013.1')

url_base = 'http://tarballs.openstack.org/ceilometer/ceilometer-%s.tar.gz'


def directories(target_dir):
    return [dirpath
            for dirpath, dirnames, filenames in os.walk(target_dir)]


setuptools.setup(

    name='ceilometer',
    version=version,

    description='cloud computing metering',

    author='OpenStack',
    author_email='ceilometer@lists.launchpad.net',

    url='https://launchpad.net/ceilometer',
    download_url=url_base % version,

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Setuptools Plugin',
        'Environment :: OpenStack',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: System :: Monitoring',
    ],

    packages=setuptools.find_packages(exclude=['bin']),
    cmdclass=common_setup.get_cmdclass(),
    package_data={
        "ceilometer":
        directories("ceilometer/api/static")
        + directories("ceilometer/api/templates"),
    },
    include_package_data=True,

    test_suite='nose.collector',

    scripts=['bin/ceilometer-agent-compute',
             'bin/ceilometer-agent-central',
             'bin/ceilometer-api',
             'bin/ceilometer-collector',
             'bin/ceilometer-dbsync'],

    py_modules=[],

    install_requires=requires,
    dependency_links=depend_links,

    zip_safe=False,

    entry_points=textwrap.dedent("""
    [ceilometer.collector]
    instance = ceilometer.compute.notifications:Instance
    instance_flavor = ceilometer.compute.notifications:InstanceFlavor
    memory = ceilometer.compute.notifications:Memory
    vcpus = ceilometer.compute.notifications:VCpus
    disk_root_size = ceilometer.compute.notifications:RootDiskSize
    disk_ephemeral_size = ceilometer.compute.notifications:EphemeralDiskSize
    volume = ceilometer.volume.notifications:Volume
    volume_size = ceilometer.volume.notifications:VolumeSize
    image_crud = ceilometer.image.notifications:ImageCRUD
    image = ceilometer.image.notifications:Image
    image_size = ceilometer.image.notifications:ImageSize
    image_download = ceilometer.image.notifications:ImageDownload
    image_serve = ceilometer.image.notifications:ImageServe
    network = ceilometer.network.notifications:Network
    subnet = ceilometer.network.notifications:Subnet
    port = ceilometer.network.notifications:Port
    router = ceilometer.network.notifications:Router
    floatingip = ceilometer.network.notifications:FloatingIP

    [ceilometer.poll.compute]
    diskio = ceilometer.compute.pollsters:DiskIOPollster
    cpu = ceilometer.compute.pollsters:CPUPollster
    net = ceilometer.compute.pollsters:NetPollster
    instance = ceilometer.compute.pollsters:InstancePollster

    [ceilometer.poll.central]
    network_floatingip = ceilometer.network.floatingip:FloatingIPPollster
    image = ceilometer.image.glance:ImagePollster
    objectstore = ceilometer.objectstore.swift:SwiftPollster
    kwapi = ceilometer.energy.kwapi:KwapiPollster

    [ceilometer.storage]
    log = ceilometer.storage.impl_log:LogStorage
    mongodb = ceilometer.storage.impl_mongodb:MongoDBStorage
    mysql = ceilometer.storage.impl_sqlalchemy:SQLAlchemyStorage
    postgresql = ceilometer.storage.impl_sqlalchemy:SQLAlchemyStorage
    sqlite = ceilometer.storage.impl_sqlalchemy:SQLAlchemyStorage
    test = ceilometer.storage.impl_test:TestDBStorage
    hbase = ceilometer.storage.impl_hbase:HBaseStorage

    [ceilometer.compute.virt]
    libvirt = ceilometer.compute.virt.libvirt.inspector:LibvirtInspector

    [ceilometer.transformer]
    accumulator = ceilometer.transformer.accumulator:TransformerAccumulator

    [ceilometer.publisher]
    meter_publisher = ceilometer.publisher.meter_publish:MeterPublisher

    [paste.filter_factory]
    swift=ceilometer.objectstore.swift_middleware:filter_factory
    """),
)
