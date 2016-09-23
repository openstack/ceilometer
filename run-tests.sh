#!/bin/bash
set -e
set -x

# Use a mongodb backend by default
if [ -z $CEILOMETER_TEST_BACKEND ]; then
    CEILOMETER_TEST_BACKEND="mongodb"
fi

echo
echo "OS_TEST_PATH: $OS_TEST_PATH"
echo "CEILOMETER_TEST_BACKEND: $CEILOMETER_TEST_BACKEND"
echo "CEILOMETER_TEST_DEBUG: $CEILOMETER_TEST_DEBUG"
echo

if [ "$CEILOMETER_TEST_BACKEND" == "none" ]; then
    if [ "$CEILOMETER_TEST_DEBUG" == "True" ]; then
        oslo_debug_helper $*
    else
        ./tools/pretty_tox.sh $*
    fi
else
    for backend in $CEILOMETER_TEST_BACKEND; do
        if [ "$CEILOMETER_TEST_DEBUG" == "True" ]; then
            pifpaf --debug run $backend oslo_debug_helper $*
        else
            pifpaf run $backend ./tools/pretty_tox.sh $*
        fi
    done
fi
