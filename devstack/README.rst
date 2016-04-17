===============================
Enabling Ceilometer in DevStack
===============================

1. Download Devstack::

    git clone https://git.openstack.org/openstack-dev/devstack
    cd devstack

2. Add this repo as an external repository in ``local.conf`` file::

    [[local|localrc]]
    enable_plugin ceilometer https://git.openstack.org/openstack/ceilometer

   To use stable branches, make sure devstack is on that branch, and specify
   the branch name to enable_plugin, for example::

    enable_plugin ceilometer https://git.openstack.org/openstack/ceilometer stable/mitaka

   There are some options, such as CEILOMETER_BACKEND, defined in
   ``ceilometer/devstack/settings``, they can be used to configure the
   installation of Ceilometer. If you don't want to use their default value,
   you can set a new one in ``local.conf``.

3. Run ``stack.sh``.
