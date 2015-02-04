#!/bin/bash
set -e

source functions.sh

if [ "$1" = "--coverage" ]; then
    COVERAGE_ARG="$1"
    shift
fi

export PATH=$PATH:/usr/share/elasticsearch/bin

check_for_cmd elasticsearch

# check for Java
if [ -x "$JAVA_HOME/bin/java" ]; then
    JAVA="$JAVA_HOME/bin/java"
else
    JAVA=`which java`
fi

if [ ! -x "$JAVA" ]; then
    echo "Could not find any executable java binary. Please install java in your PATH or set JAVA_HOME"
    exit 1
fi

# Start ElasticSearch process for tests
ES_DATA=`mktemp -d /tmp/CEILO-ES-XXXXX`
ES_PORT=9200
ES_PID=${ES_DATA}/elasticsearch.pid
elasticsearch -p ${ES_PID} -Des.http.port=${ES_PORT} -Des.path.logs=${ES_DATA}/logs -Des.path.data=${ES_DATA} -Des.path.conf=/etc/elasticsearch &> ${ES_DATA}/out &
# Wait for ElasticSearch to start listening to connections
sleep 3
wait_for_line "started" ${ES_DATA}/out
export CEILOMETER_TEST_ES_URL="es://localhost:${ES_PORT}"

# Yield execution to venv command
$*

# Kill ElasticSearch
kill $(cat ${ES_PID})
