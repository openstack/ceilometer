#!/bin/bash
#
#

set -o errexit

source $GRENADE_DIR/grenaderc
source $GRENADE_DIR/functions

# We need base DevStack functions for this.
# TODO(chdent): This relies on the fact that for now base devstack is
# hosting ceilometer itself. Once M* starts this will need to be smarter.
source $BASE_DEVSTACK_DIR/functions
source $BASE_DEVSTACK_DIR/stackrc # needed for status directory
source $BASE_DEVSTACK_DIR/lib/tls
source $BASE_DEVSTACK_DIR/lib/apache
source $BASE_DEVSTACK_DIR/lib/ceilometer

set -o xtrace

stop_ceilometer
