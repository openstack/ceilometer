#!/bin/bash
set -e

function clean_exit(){
    local error_code="$?"
    rm -rf ${MONGO_DATA}
    if test -n "$CEILOMETER_TEST_HBASE_URL"
    then
            python tools/test_hbase_table_utils.py --clear
    fi
    kill $(jobs -p)
    return $error_code
}

# Setup MongoDB test server
MONGO_DATA=`mktemp -d CEILO-MONGODB-XXXXX`
MONGO_PORT=29000
trap "clean_exit" EXIT
mkfifo ${MONGO_DATA}/out
export PATH=${PATH:+$PATH:}/sbin:/usr/sbin
if ! which mongod >/dev/null 2>&1
then
    echo "Could not find mongod command" 1>&2
    exit 1
fi
mongod --maxConns 32 --nojournal --noprealloc --smallfiles --quiet --noauth --port ${MONGO_PORT} --dbpath "${MONGO_DATA}" --bind_ip localhost --config /dev/null &>${MONGO_DATA}/out &
# Wait for Mongo to start listening to connections
while read line
do
    echo "$line" | grep -q "waiting for connections on port ${MONGO_PORT}" && break
done < ${MONGO_DATA}/out
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
