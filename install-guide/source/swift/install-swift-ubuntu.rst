Enable Object Storage meters for Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Telemetry uses a combination of polling and notifications to collect
Object Storage meters.

.. note::

   Your environment must include the Object Storage service.

.. include:: install-swift-prereq-common.inc

Install components
------------------

* Install the packages:

  .. code-block:: console

     # apt-get install python-ceilometermiddleware

.. include:: install-swift-config-common.inc

Finalize installation
---------------------

* Restart the Object Storage proxy service:

  .. code-block:: console

     # service swift-proxy restart
