#!/bin/sh
# Wrap nosetests to force it to enable global site-packages until
# https://bitbucket.org/hpk42/tox/issue/32 is released.

set -x

rm -rf cover
if [ ! -z "$VIRTUAL_ENV" ]
then
	rm -f $VIRTUAL_ENV/lib/python*/no-global-site-packages.txt
fi

nosetests "$@"
