..
      Copyright 2012 Nicolas Barcet for Canonical

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

Initial setup
=============

If you are not yet familiar with ceilometer's architecture, it would be
advisable that you start by reading the blueprint at http://wiki.openstack.org/EfficientMetering, and more specifically the architecture which has been agreed on
at: http://wiki.openstack.org/EfficientMetering/ArchitectureProposalV1.

In order to contribute to the ceilometer project, you will also need to:

1. Have signed OpenStack's contributor's agreement. Refer to http://wiki.openstack.org/CLA for more information.

2. Be familiar with git and the OpenStack Gerrit review process, see http://wiki.openstack.org/GerritWorkflow. 

.. note:: 

	Currently the ceilometer project is using StackForge, a
	system for code reviews identical to the OpenStack contribution infrastructure. 

Setting up the project
======================

1. The first thing you will need to do is to clone the ceilometer project on your local machine::

    git clone https://github.com/stackforge/ceilometer.git

2. Once this is done, you need to setup the review process::

    git remote add gerrit ssh://<username>@review.stackforge.org:29418/stackforge/ceilometer.git

3. Create a topic branch and switch to it::

    git checkout -b TOPIC-BRANCH
