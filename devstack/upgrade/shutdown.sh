#!/bin/bash
#
#

set -o errexit

source $GRENADE_DIR/grenaderc
source $GRENADE_DIR/functions

source $BASE_DEVSTACK_DIR/functions
source $BASE_DEVSTACK_DIR/stackrc # needed for status directory
source $BASE_DEVSTACK_DIR/lib/tls
source $BASE_DEVSTACK_DIR/lib/apache

# Locate the ceilometer plugin and get its functions
CEILOMETER_DEVSTACK_DIR=$(dirname $(dirname $0))
source $CEILOMETER_DEVSTACK_DIR/plugin.sh

set -o xtrace

stop_ceilometer

# ensure everything is stopped

SERVICES_DOWN="ceilometer-acompute ceilometer-acentral ceilometer-aipmi ceilometer-anotification ceilometer-collector ceilometer-api"

ensure_services_stopped $SERVICES_DOWN
