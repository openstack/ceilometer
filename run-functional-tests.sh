#!/bin/bash -x
set -e
# Use a mongodb backend by default


if [ -z $CEILOMETER_TEST_BACKEND ]; then
    CEILOMETER_TEST_BACKEND="mongodb"
fi
echo $CEILOMETER_TEST_BACKEND
for backend in $CEILOMETER_TEST_BACKEND; do
    ./setup-test-env-${backend}.sh ./tools/pretty_tox.sh $*
done
