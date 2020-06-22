.. _configuring:

================================
Ceilometer Configuration Options
================================

Ceilometer Sample Configuration File
====================================

Configure Ceilometer by editing /etc/ceilometer/ceilometer.conf.

No config file is provided with the source code, it will be created during
the installation. In case where no configuration file was installed, one
can be easily created by running::

    oslo-config-generator \
        --config-file=/etc/ceilometer/ceilometer-config-generator.conf \
        --output-file=/etc/ceilometer/ceilometer.conf

.. only:: html

   The following is a sample Ceilometer configuration for adaptation and use.
   It is auto-generated from Ceilometer when this documentation is built, and
   can also be viewed in `file form <_static/ceilometer.conf.sample>`_.

   .. literalinclude:: ../_static/ceilometer.conf.sample
