#!/bin/sh
TEMPDIR=`mktemp -d /tmp/ceilometer-check-config-XXXXXX`
CFGFILE=ceilometer.conf.sample
tools/config/generate_sample.sh -b ./ -p ceilometer -o $TEMPDIR
if ! diff $TEMPDIR/$CFGFILE etc/ceilometer/$CFGFILE
then
    echo "E: ceilometer.conf.sample is not up to date, please run tools/config/generate_sample.sh"
    exit 42
fi
