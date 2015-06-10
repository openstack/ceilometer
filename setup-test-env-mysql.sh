#!/bin/bash
set -e

source functions.sh

if [ "$1" = "--coverage" ]; then
	COVERAGE_ARG="$1"
	shift
fi

export PATH=${PATH:+$PATH:}/sbin:/usr/sbin

# On systems like Fedora here's where mysqld can be found
export PATH=$PATH:/usr/libexec

check_for_cmd mysqld

# Start MySQL process for tests
MYSQL_DATA=`mktemp -d /tmp/CEILO-MYSQL-XXXXX`
trap "clean_exit ${MYSQL_DATA}" EXIT
mkfifo ${MYSQL_DATA}/out
mysqld --datadir=${MYSQL_DATA} --pid-file=${MYSQL_DATA}/mysql.pid --socket=${MYSQL_DATA}/mysql.socket --skip-networking --skip-grant-tables &> ${MYSQL_DATA}/out &
# Wait for MySQL to start listening to connections
wait_for_line "mysqld: ready for connections." ${MYSQL_DATA}/out
export CEILOMETER_TEST_MYSQL_URL="mysql+pymysql://root@localhost/template1?unix_socket=${MYSQL_DATA}/mysql.socket&charset=utf8"

# Yield execution to venv command
$*
