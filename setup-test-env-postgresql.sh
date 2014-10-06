#!/bin/bash
set -e

source functions.sh

if [ "$1" = "--coverage" ]; then
	COVERAGE_ARG="$1"
	shift
fi

#export PATH=${PATH:+$PATH:}/sbin:/usr/sbin

check_for_cmd pg_config

# Start PostgreSQL process for tests
PGSQL_DATA=`mktemp -d /tmp/CEILO-PGSQL-XXXXX`
trap "clean_exit ${PGSQL_DATA}" EXIT
PGSQL_PATH=`pg_config --bindir`
${PGSQL_PATH}/initdb ${PGSQL_DATA}
mkfifo ${PGSQL_DATA}/out
${PGSQL_PATH}/postgres -N 100 -F -k ${PGSQL_DATA} -D ${PGSQL_DATA} -p 9823 &> ${PGSQL_DATA}/out &
# Wait for PostgreSQL to start listening to connections
wait_for_line "database system is ready to accept connections" ${PGSQL_DATA}/out
export CEILOMETER_TEST_PGSQL_URL="postgresql:///?host=${PGSQL_DATA}&port=9823&dbname=template1"

# Yield execution to venv command
$*
