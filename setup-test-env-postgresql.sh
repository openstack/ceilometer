#!/bin/bash
set -e

source functions.sh

if [ "$1" = "--coverage" ]; then
	COVERAGE_ARG="$1"
	shift
fi

function clean_exit_pgsql(){
    ret=$?
    ${1}/pg_ctl -w -D ${2} -o "-p ${3}" stop
    rm -rf ${2}
    return ${ret}
}


#export PATH=${PATH:+$PATH:}/sbin:/usr/sbin

check_for_cmd pg_config

# Start PostgreSQL process for tests
PGSQL_DATA=`mktemp -d /tmp/CEILO-PGSQL-XXXXX`
PGSQL_PATH=`pg_config --bindir`
PGSQL_PORT=9823
${PGSQL_PATH}/initdb -E UTF8 ${PGSQL_DATA}
trap "clean_exit_pgsql ${PGSQL_PATH} ${PGSQL_DATA} ${PGSQL_PORT}" EXIT

LANGUAGE=C ${PGSQL_PATH}/pg_ctl -w -D ${PGSQL_DATA} -o "-F -k ${PGSQL_DATA} -p ${PGSQL_PORT}" start
export CEILOMETER_TEST_PGSQL_URL="postgresql:///?host=${PGSQL_DATA}&port=${PGSQL_PORT}&dbname=template1"

# Yield execution to venv command
$*
