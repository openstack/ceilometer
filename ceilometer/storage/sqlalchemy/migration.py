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


def paged(query, size=1000):
    """Page query results

    :param query: the SQLAlchemy query to execute
    :param size: the max page size
    return: generator with query data
    """
    offset = 0
    while True:
        page = query.offset(offset).limit(size).execute()
        if page.rowcount <= 0:
            # There are no more rows
            break
        for row in page:
            yield row
        offset += size
