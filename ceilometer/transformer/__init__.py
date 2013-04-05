# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel Corp.
#
# Author: Yunhong Jiang <yunhong.jiang@intel.com>
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

from stevedore import extension


class TransformerExtensionManager(extension.ExtensionManager):

    def __init__(self, namespace):
        super(TransformerExtensionManager, self).__init__(
            namespace=namespace,
            invoke_on_load=False,
            invoke_args=(),
            invoke_kwds={}
        )
        self.by_name = dict((e.name, e) for e in self.extensions)

    def get_ext(self, name):
        return self.by_name[name]
