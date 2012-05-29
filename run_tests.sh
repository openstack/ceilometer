#!/bin/sh
# Simple test runner, should be replaced with tox

rm -rf cover
nosetests -P -d -v --cover-erase --with-coverage --cover-package=ceilometer --cover-inclusive tests
tox -e pep8
