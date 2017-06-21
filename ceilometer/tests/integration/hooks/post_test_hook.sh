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
    set +e

    echo "* Message queue status:"
    sudo rabbitmqctl list_queues | grep -e \\.sample -e \\.info

    source $BASE/new/devstack/openrc admin admin

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

    echo "* Unprocessed measures:"
    for key in $(redis-cli --scan --pattern 'incoming*'); do echo -n $key && redis-cli llen $key; done

    set -e
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


# Run tests with tempest
sudo chown -R tempest:stack $BASE/new/tempest
sudo chown -R tempest:stack $BASE/data/tempest
cd $BASE/new/tempest
set +e
sudo -H -u tempest OS_TEST_TIMEOUT=$TEMPEST_OS_TEST_TIMEOUT tox -eall-plugin -- ceilometer.tests.tempest.scenario.test_telemetry_integration --concurrency=$TEMPEST_CONCURRENCY
EXIT_CODE=$?
set -e
export_subunit_data "all-plugin"
generate_reports_and_maybe_exit $EXIT_CODE

exit $EXIT_CODE
