# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Tests for converters for producing compute counter messages from
notification events.
"""

from ceilometer import signature


def test_change_key():
    sig1 = signature.compute_signature({'a': 'A', 'b': 'B'})
    sig2 = signature.compute_signature({'A': 'A', 'b': 'B'})
    assert sig1 != sig2


def test_change_value():
    sig1 = signature.compute_signature({'a': 'A', 'b': 'B'})
    sig2 = signature.compute_signature({'a': 'a', 'b': 'B'})
    assert sig1 != sig2


def test_same():
    sig1 = signature.compute_signature({'a': 'A', 'b': 'B'})
    sig2 = signature.compute_signature({'a': 'A', 'b': 'B'})
    assert sig1 == sig2
