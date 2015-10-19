===============================
Enabling Ceilometer in DevStack
===============================

1. Download Devstack::

    git clone https://git.openstack.org/openstack-dev/devstack
    cd devstack

2. Add this repo as an external repository in ``local.conf`` file::

    [[local|localrc]]
    enable_plugin ceilometer https://git.openstack.org/openstack/ceilometer

3. Run ``stack.sh``.
