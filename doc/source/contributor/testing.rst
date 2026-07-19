..
      Copyright 2012 New Dream Network, LLC (DreamHost)

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=================
Running the Tests
=================

Ceilometer includes an extensive set of automated unit tests which are
run through tox_.

1. Install ``tox``::

   $ sudo pip install tox

2. Run the unit and code-style tests::

   $ cd /opt/stack/ceilometer
   $ tox -e py3,pep8

As tox is a wrapper around stestr, it also accepts the same flags as stestr.
See the `stestr documentation`_ for details about these additional flags.

.. _stestr documentation: https://stestr.readthedocs.io/en/latest/

Use a double hyphen to pass options to stestr. For example, to run only tests
under tests/unit/image::

  $ tox -e py3 -- image

To debug tests (ie. break into pdb debugger), you can use ''debug'' tox
environment. Here's an example, passing the name of a test since you'll
normally only want to run the test that hits your breakpoint::

  $ tox -e debug ceilometer.tests.unit.test_bin

For reference, the ``debug`` tox environment implements the instructions
here: https://docs.openstack.org/oslotest/latest/user/debugging.html

.. _tox: https://tox.readthedocs.io/en/latest/
