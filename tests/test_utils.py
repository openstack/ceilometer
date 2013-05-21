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
"""Tests for ceilometer/utils.py
"""

from ceilometer import utils


def test_recursive_keypairs():
    data = {'a': 'A',
            'b': 'B',
            'nested': {'a': 'A',
                       'b': 'B',
                       },
            }
    pairs = list(utils.recursive_keypairs(data))
    assert pairs == [('a', 'A'),
                     ('b', 'B'),
                     ('nested:a', 'A'),
                     ('nested:b', 'B'),
                     ]
