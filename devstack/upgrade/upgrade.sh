#!/usr/bin/env bash

# ``upgrade-ceilometer``

echo "*********************************************************************"
echo "Begin $0"
echo "*********************************************************************"

# Clean up any resources that may be in use
cleanup() {
    set +o errexit

    echo "*********************************************************************"
    echo "ERROR: Abort $0"
    echo "*********************************************************************"

    # Kill ourselves to signal any calling process
    trap 2; kill -2 $$
}

trap cleanup SIGHUP SIGINT SIGTERM

# Keep track of the grenade directory
RUN_DIR=$(cd $(dirname "$0") && pwd)

# Source params
source $GRENADE_DIR/grenaderc

# Import common functions
source $GRENADE_DIR/functions

# This script exits on an error so that errors don't compound and you see
# only the first error that occurred.
set -o errexit

# Save mongodb state (replace with snapshot)
# TODO(chdent): There used to be a 'register_db_to_save ceilometer'
# which may wish to consider putting back in.
if grep -q 'connection *= *mongo' /etc/ceilometer/ceilometer.conf; then
    mongodump --db ceilometer --out $SAVE_DIR/ceilometer-dump.$BASE_RELEASE
fi

# Upgrade Ceilometer
# ==================
# Locate ceilometer devstack plugin, the directory above the
# grenade plugin.
CEILOMETER_DEVSTACK_DIR=$(dirname $(dirname $0))

# Get functions from current DevStack
source $TARGET_DEVSTACK_DIR/functions
source $TARGET_DEVSTACK_DIR/stackrc
source $TARGET_DEVSTACK_DIR/lib/apache

# Get ceilometer functions from devstack plugin
source $CEILOMETER_DEVSTACK_DIR/settings

# Print the commands being run so that we can see the command that triggers
# an error.
set -o xtrace

# Install the target ceilometer
source $CEILOMETER_DEVSTACK_DIR/plugin.sh stack install

# calls upgrade-ceilometer for specific release
upgrade_project ceilometer $RUN_DIR $BASE_DEVSTACK_BRANCH $TARGET_DEVSTACK_BRANCH

# Migrate the database
# NOTE(chdent): As we evolve BIN_DIR is likely to be defined, but
# currently it is not.
CEILOMETER_BIN_DIR=$(dirname $(which ceilometer-dbsync))
$CEILOMETER_BIN_DIR/ceilometer-dbsync || die $LINENO "DB sync error"

# Start Ceilometer
start_ceilometer

# Note these are process names, not service names
# Note(liamji): Disable the test for
# "ceilometer-polling --polling-namespaces ipmi". In the test environment,
# the impi is not ready. The ceilometer-polling should fail.
ensure_services_started "ceilometer-polling --polling-namespaces compute" \
                        "ceilometer-polling --polling-namespaces central" \
                        ceilometer-agent-notification \
                        ceilometer-api \
                        ceilometer-collector

# Save mongodb state (replace with snapshot)
if grep -q 'connection *= *mongo' /etc/ceilometer/ceilometer.conf; then
    mongodump --db ceilometer --out $SAVE_DIR/ceilometer-dump.$TARGET_RELEASE
fi


set +o xtrace
echo "*********************************************************************"
echo "SUCCESS: End $0"
echo "*********************************************************************"
