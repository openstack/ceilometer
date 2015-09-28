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

import os

import happybase


class MockHBaseTable(happybase.Table):

    def __init__(self, name, connection, data_prefix):
        # data_prefix is added to all rows which are written
        # in this test. It allows to divide data from different tests
        self.data_prefix = data_prefix
        # We create happybase Table with prefix from
        # CEILOMETER_TEST_HBASE_TABLE_PREFIX
        prefix = os.getenv("CEILOMETER_TEST_HBASE_TABLE_PREFIX", 'test')
        separator = os.getenv(
            "CEILOMETER_TEST_HBASE_TABLE_PREFIX_SEPARATOR", '_')
        super(MockHBaseTable, self).__init__(
            "%s%s%s" % (prefix, separator, name),
            connection)

    def put(self, row, *args, **kwargs):
        row = self.data_prefix + row
        return super(MockHBaseTable, self).put(row, *args,
                                               **kwargs)

    def scan(self, row_start=None, row_stop=None, row_prefix=None,
             columns=None, filter=None, timestamp=None,
             include_timestamp=False, batch_size=10, scan_batching=None,
             limit=None, sorted_columns=False):
        # Add data prefix for row parameters
        # row_prefix could not be combined with row_start or row_stop
        if not row_start and not row_stop:
            row_prefix = self.data_prefix + (row_prefix or "")
            row_start = None
            row_stop = None
        elif row_start and not row_stop:
            # Adding data_prefix to row_start and row_stop does not work
            # if it looks like row_start = %data_prefix%foo,
            # row_stop = %data_prefix, because row_start > row_stop
            filter = self._update_filter_row(filter)
            row_start = self.data_prefix + row_start
        else:
            row_start = self.data_prefix + (row_start or "")
            row_stop = self.data_prefix + (row_stop or "")
        gen = super(MockHBaseTable, self).scan(row_start, row_stop,
                                               row_prefix, columns,
                                               filter, timestamp,
                                               include_timestamp, batch_size,
                                               scan_batching, limit,
                                               sorted_columns)
        data_prefix_len = len(self.data_prefix)
        # Restore original row format
        for row, data in gen:
            yield (row[data_prefix_len:], data)

    def row(self, row, *args, **kwargs):
        row = self.data_prefix + row
        return super(MockHBaseTable, self).row(row, *args, **kwargs)

    def delete(self, row, *args, **kwargs):
        row = self.data_prefix + row
        return super(MockHBaseTable, self).delete(row, *args, **kwargs)

    def _update_filter_row(self, filter):
        if filter:
            return "PrefixFilter(%s) AND %s" % (self.data_prefix, filter)
        else:
            return "PrefixFilter(%s)" % self.data_prefix
