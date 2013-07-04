#!/bin/sh
TMPFILE=`mktemp`
trap "rm -f ${TMPFILE}" EXIT
tools/conf/generate_sample.sh "${TMPFILE}"
if ! diff "${TMPFILE}" etc/ceilometer/ceilometer.conf.sample
then
    echo "E: ceilometer.conf.sample is not up to date, please run tools/conf/generate_sample.sh"
    exit 42
fi
