Ceilometer Style Commandments
=============================

- Step 1: Read the OpenStack Style Commandments
  https://docs.openstack.org/hacking/latest/
- Step 2: Read on

Ceilometer Specific Commandments
--------------------------------

- [C301] LOG.warn() is not allowed. Use LOG.warning()
- [C302] Deprecated library function os.popen()

Running Unit Tests
------------------

Tests are run using ``tox``::

    tox -e py3

By default, log output from tests flows to stderr at ``INFO`` level, matching
the behaviour of the master branch.  Two environment variables control this:

``OS_LOG_CAPTURE``
    When set to ``True`` (or ``true``, ``1``, ``yes``), the
    ``StandardLogging`` fixture is activated.  Log records are captured in an
    in-memory buffer rather than printed to the terminal during the run.  On
    test failure the captured output is surfaced automatically, making it
    easier to diagnose the failure without noise from passing tests.


``OS_DEBUG``
    When set to ``True`` (or ``true``, ``1``, ``yes``), the log level is
    raised to ``DEBUG``.

Typical workflows::

    # Quiet run — failures show captured INFO logs
    OS_LOG_CAPTURE=1 tox -e py3

    # Quiet run — failures show captured DEBUG logs
    OS_LOG_CAPTURE=1 OS_DEBUG=True tox -e py3

    # Live log output to stderr (default)
    tox -e py3

Creating Unit Tests
-------------------
For every new feature, unit tests should be created that both test and
(implicitly) document the usage of said feature. If submitting a patch for a
bug that had no unit test, a new passing unit test should be added. If a
submitted bug fix does have a unit test, be sure to add a new one that fails
without the patch and passes with the patch.

All unittest classes must ultimately inherit from oslotest.base.BaseTestCase.

All setUp and tearDown methods must upcall using the super() method.
tearDown methods should be avoided and addCleanup calls should be preferred.
Never manually create tempfiles. Always use the tempfile fixtures from
the fixture library to ensure that they are cleaned up.
