..
      Copyright 2013 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

===================================
 Installing the API behind mod_wsgi
===================================

Ceilometer comes with a few example files for configuring the API
service to run behind Apache with ``mod_wsgi``.

app.wsgi
========

The file ``ceilometer/api/app.wsgi`` sets up the V2 API WSGI
application. The file is installed with the rest of the ceilometer
application code, and should not need to be modified.

etc/apache2/ceilometer
======================

The ``etc/apache2/ceilometer`` file contains example settings that
work with a copy of ceilometer installed via devstack.

.. literalinclude:: ../../../etc/apache2/ceilometer

1. On deb-based systems copy or symlink the file to
   ``/etc/apache2/sites-available``. For rpm-based systems the file will go in
   ``/etc/httpd/conf.d``.

2. Modify the ``WSGIDaemonProcess`` directive to set the ``user`` and
   ``group`` values to a appropriate user on your server. In many
   installations ``ceilometer`` will be correct.

3. Enable the ceilometer site. On deb-based systems::

      $ a2ensite ceilometer
      $ service apache2 reload

   On rpm-based systems::

      $ service httpd reload


Limitation
==========

As Ceilometer is using Pecan and Pecan's DebugMiddleware doesn't support
multiple processes, there is no way to set debug mode in the multiprocessing
case. To allow multiple processes the DebugMiddleware may be turned off by
setting ``pecan_debug`` to ``False`` in the ``api`` section of
``ceilometer.conf``.

For other WSGI setup you can refer to the `pecan deployment`_ documentation.
.. _`pecan deployment`: http://pecan.readthedocs.org/en/latest/deployment.html
