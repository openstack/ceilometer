#!/bin/bash
set -e

source functions.sh

if [ "$1" = "--coverage" ]; then
	COVERAGE_ARG="$1"
	shift
fi

export PATH=${PATH:+$PATH:}/sbin:/usr/sbin
check_for_cmd mongod

# Start MongoDB process for tests
MONGO_DATA=`mktemp -d /tmp/CEILO-MONGODB-XXXXX`
MONGO_PORT=29000
trap "clean_exit ${MONGO_DATA}" EXIT
mkfifo ${MONGO_DATA}/out
mongod --maxConns 32 --nojournal --noprealloc --smallfiles --quiet --noauth --port ${MONGO_PORT} --dbpath "${MONGO_DATA}" --bind_ip localhost --config /dev/null &>${MONGO_DATA}/out &
# Wait for Mongo to start listening to connections
wait_for_line "waiting for connections on port ${MONGO_PORT}" ${MONGO_DATA}/out
# Read the fifo for ever otherwise mongod would block
cat ${MONGO_DATA}/out > /dev/null &
export CEILOMETER_TEST_MONGODB_URL="mongodb://localhost:${MONGO_PORT}/ceilometer"
if test -n "$CEILOMETER_TEST_HBASE_URL"
then
    export CEILOMETER_TEST_HBASE_TABLE_PREFIX=$(hexdump -n 16 -v -e '/1 "%02X"' /dev/urandom)
    python tools/test_hbase_table_utils.py --upgrade
fi

# Yield execution to venv command
$*
