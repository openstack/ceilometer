#!/bin/bash -x
set -e
# Use a mongodb backend by default

if [ -z $CEILOMETER_TEST_BACKEND ]; then
    CEILOMETER_TEST_BACKEND="mongodb"
fi

for backend in $CEILOMETER_TEST_BACKEND; do
    overtest $backend ./tools/pretty_tox.sh $*
done
