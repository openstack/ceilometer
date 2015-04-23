# -*- encoding: utf-8 -*-
#
# Copyright 2014 OpenStack Foundation
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

import eventlet
# NOTE(jd) We need to monkey patch the socket and select module for,
# at least, oslo.messaging, otherwise everything's blocked on its
# first read() or select(), thread need to be patched too, because
# oslo.messaging use threading.local
eventlet.monkey_patch(socket=True, select=True, thread=True, time=True)
