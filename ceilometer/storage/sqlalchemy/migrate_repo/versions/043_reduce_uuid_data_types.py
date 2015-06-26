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


def upgrade(migrate_engine):
    # NOTE(gordc): this is a noop script to handle bug1468916
    # previous lowering of id length will fail if db contains data longer.
    # this skips migration for those failing. the next script will resize
    # if this original migration passed.
    pass
