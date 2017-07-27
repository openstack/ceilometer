.. _install_controller:

Install and Configure Controller Services
=========================================

This section assumes that you already have a working OpenStack
environment with at least the following components installed:
Compute, Image Service, Identity.

Note that installation and configuration vary by distribution.

Ceilometer
----------

.. toctree::
   :maxdepth: 1

   install-base-obs.rst
   install-base-rdo.rst
   install-base-ubuntu.rst

Additional steps are required to configure services to interact with
ceilometer:

Cinder
------

.. toctree::
   :maxdepth: 1

   cinder/install-cinder-obs.rst
   cinder/install-cinder-rdo.rst
   cinder/install-cinder-ubuntu.rst

Glance
------

.. toctree::
   :maxdepth: 1

   glance/install-glance-obs.rst
   glance/install-glance-rdo.rst
   glance/install-glance-ubuntu.rst

Heat
----

.. toctree::
   :maxdepth: 1

   heat/install-heat-obs.rst
   heat/install-heat-rdo.rst
   heat/install-heat-ubuntu.rst

Keystone
--------

To enable auditing of API requests, Keystone provides middleware which captures
API requests to a service and emits data to Ceilometer. Instructions to enable
this functionality is available in `Keystone's developer documentation
<https://docs.openstack.org/keystonemiddleware/latest/audit.html>`_.
Ceilometer will captures this information as ``audit.http.*`` events.

Neutron
-------

.. toctree::
   :maxdepth: 1

   neutron/install-neutron-obs.rst
   neutron/install-neutron-rdo.rst
   neutron/install-neutron-ubuntu.rst

Swift
-----

.. toctree::
   :maxdepth: 1

   swift/install-swift-obs.rst
   swift/install-swift-rdo.rst
   swift/install-swift-ubuntu.rst
