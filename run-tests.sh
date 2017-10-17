#!/bin/bash
set -e
set -x

echo
echo "OS_TEST_PATH: $OS_TEST_PATH"
echo "CEILOMETER_TEST_DEBUG: $CEILOMETER_TEST_DEBUG"
echo

if [ "$CEILOMETER_TEST_DEBUG" == "True" ]; then
    oslo_debug_helper $*
else
    ./tools/pretty_tox.sh $*
fi
