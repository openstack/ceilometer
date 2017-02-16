#!/bin/bash -xe

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# This script is executed inside post_test_hook function in devstack gate.

function export_subunit_data {
    target="$1"
    if [ -f .testrepository/0 ]; then
        sudo testr last --subunit > $WORKSPACE/testrepository.subunit.$target
    fi
}

function generate_testr_results {
    cat $WORKSPACE/testrepository.subunit.* | sudo tee $BASE/logs/testrepository.subunit
    sudo /usr/os-testr-env/bin/subunit2html $BASE/logs/testrepository.subunit $BASE/logs/testr_results.html
    sudo gzip -9 $BASE/logs/testrepository.subunit
    sudo gzip -9 $BASE/logs/testr_results.html
    sudo chown jenkins:jenkins $BASE/logs/testrepository.subunit.gz $BASE/logs/testr_results.html.gz
    sudo chmod a+r $BASE/logs/testrepository.subunit.gz $BASE/logs/testr_results.html.gz
}

function generate_telemetry_report(){
    set +x

    echo "* Message queue status:"
    sudo rabbitmqctl list_queues | grep -e \\.sample -e \\.info

    echo "* Heat stack:"
    openstack stack show integration_test
    echo "* Alarm list:"
    aodh alarm list
    echo "* Event list:"
    ceilometer event-list -q 'event_type=string::compute.instance.create.end'
    echo "* Nova instance list:"
    openstack server list

    echo "* Gnocchi instance list:"
    gnocchi resource list -t instance
    for instance_id in $(openstack server list -f value -c ID); do
        echo "* Nova instance detail:"
        openstack server show $instance_id
        echo "* Gnocchi instance detail:"
        gnocchi resource show -t instance $instance_id
        echo "* Gnocchi measures for instance ${instance_id}:"
        gnocchi measures show -r $instance_id cpu_util
    done

    gnocchi status

    # Be sure to source Gnocchi settings before
    source $BASE/new/gnocchi/devstack/settings
    echo "* Unprocessed measures:"
    sudo find $GNOCCHI_DATA_DIR/measure

    set -x
}

function generate_reports_and_maybe_exit() {
    local ret="$1"
    if [[ $ret != 0 ]]; then
        # Collect and parse result
        generate_telemetry_report
        generate_testr_results
        exit $ret
    fi
}


# If we're running in the gate find our keystone endpoint to give to
# gabbi tests and do a chown. Otherwise the existing environment
# should provide URL and TOKEN.
if [ -d $BASE/new/devstack ]; then
    export CEILOMETER_DIR="$BASE/new/ceilometer"
    STACK_USER=stack
    sudo chown -R $STACK_USER:stack $CEILOMETER_DIR
    source $BASE/new/devstack/openrc admin admin
    # Go to the ceilometer dir
    cd $CEILOMETER_DIR
fi

openstack catalog list
export AODH_SERVICE_URL=$(openstack catalog show alarming -c endpoints -f value | awk '/public/{print $2}')
export PANKO_SERVICE_URL=$(openstack catalog show event -c endpoints -f value | awk '/public/{print $2}')
export GNOCCHI_SERVICE_URL=$(openstack catalog show metric -c endpoints -f value | awk '/public/{print $2}')
export HEAT_SERVICE_URL=$(openstack catalog show orchestration -c endpoints -f value | awk '/public/{print $2}')
export NOVA_SERVICE_URL=$(openstack catalog show compute -c endpoints -f value | awk '/public/{print $2}')
export GLANCE_IMAGE_NAME=$(openstack image list | awk '/ cirros.* /{print $4; exit}')
export ADMIN_TOKEN=$(openstack token issue -c id -f value)
export OS_AUTH_TYPE=password

# Run tests with gabbi
echo "Running telemetry integration test suite"
set +e
sudo -E -H -u ${STACK_USER:-${USER}} tox -eintegration
EXIT_CODE=$?

if [ -d $BASE/new/devstack ]; then
    export_subunit_data "integration"
    generate_reports_and_maybe_exit $EXIT_CODE

    # NOTE(sileht): on swift job permissions are wrong, I don't known why
    sudo chown -R tempest:stack $BASE/new/tempest
    sudo chown -R tempest:stack $BASE/data/tempest

    # Run tests with tempest
    cd $BASE/new/tempest
    sudo -H -u tempest OS_TEST_TIMEOUT=$TEMPEST_OS_TEST_TIMEOUT tox -eall-plugin -- ceilometer.tests.tempest.scenario.test_autoscaling --concurrency=$TEMPEST_CONCURRENCY
    EXIT_CODE=$?
    export_subunit_data "all-plugin"
    generate_reports_and_maybe_exit $EXIT_CODE
fi

exit $EXIT_CODE
