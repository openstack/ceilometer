#!/bin/sh
# Simple test runner, should be replaced with tox

nosetests -P -d -v --with-coverage --cover-package=ceilometer --cover-inclusive tests
