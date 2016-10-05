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
"""This is a very crude version of "in-memory HBase", which implements just
 enough functionality of HappyBase API to support testing of our driver.
"""

import copy
import re

from oslo_log import log
import six

import ceilometer

LOG = log.getLogger(__name__)


class MTable(object):
    """HappyBase.Table mock."""
    def __init__(self, name, families):
        self.name = name
        self.families = families
        self._rows_with_ts = {}

    def row(self, key, columns=None):
        if key not in self._rows_with_ts:
            return {}
        res = copy.copy(sorted(six.iteritems(
            self._rows_with_ts.get(key)))[-1][1])
        if columns:
            keys = res.keys()
            for key in keys:
                if key not in columns:
                    res.pop(key)
        return res

    def rows(self, keys):
        return ((k, self.row(k)) for k in keys)

    def put(self, key, data, ts=None):
        # Note: Now we use 'timestamped' but only for one Resource table.
        # That's why we may put ts='0' in case when ts is None. If it is
        # needed to use 2 types of put in one table ts=0 cannot be used.
        if ts is None:
            ts = "0"
        if key not in self._rows_with_ts:
            self._rows_with_ts[key] = {ts: data}
        else:
            if ts in self._rows_with_ts[key]:
                self._rows_with_ts[key][ts].update(data)
            else:
                self._rows_with_ts[key].update({ts: data})

    def delete(self, key):
        del self._rows_with_ts[key]

    def _get_latest_dict(self, row):
        # The idea here is to return latest versions of columns.
        # In _rows_with_ts we store {row: {ts_1: {data}, ts_2: {data}}}.
        # res will contain a list of tuples [(ts_1, {data}), (ts_2, {data})]
        # sorted by ts, i.e. in this list ts_2 is the most latest.
        # To get result as HBase provides we should iterate in reverse order
        # and get from "latest" data only key-values that are not in newer data
        data = {}
        for i in sorted(six.iteritems(self._rows_with_ts[row])):
            data.update(i[1])
        return data

    def scan(self, filter=None, columns=None, row_start=None, row_stop=None,
             limit=None):
        columns = columns or []
        sorted_keys = sorted(self._rows_with_ts)
        # copy data between row_start and row_stop into a dict
        rows = {}
        for row in sorted_keys:
            if row_start and row < row_start:
                continue
            if row_stop and row > row_stop:
                break
            rows[row] = self._get_latest_dict(row)

        if columns:
            ret = {}
            for row, data in six.iteritems(rows):
                for key in data:
                    if key in columns:
                        ret[row] = data
            rows = ret
        if filter:
            # TODO(jdanjou): we should really parse this properly,
            # but at the moment we are only going to support AND here
            filters = filter.split('AND')
            for f in filters:
                # Extract filter name and its arguments
                g = re.search("(.*)\((.*),?\)", f)
                fname = g.group(1).strip()
                fargs = [s.strip().replace('\'', '')
                         for s in g.group(2).split(',')]
                m = getattr(self, fname)
                if callable(m):
                    # overwrite rows for filtering to take effect
                    # in case of multiple filters
                    rows = m(fargs, rows)
                else:
                    raise ceilometer.NotImplementedError(
                        "%s filter is not implemented, "
                        "you may want to add it!")
        for k in sorted(rows)[:limit]:
            yield k, rows[k]

    @staticmethod
    def SingleColumnValueFilter(args, rows):
        """This is filter for testing "in-memory HBase".

        This method is called from scan() when 'SingleColumnValueFilter'
        is found in the 'filter' argument.
        """
        op = args[2]
        column = "%s:%s" % (args[0], args[1])
        value = args[3]
        if value.startswith('binary:'):
            value = value[7:]
        r = {}
        for row in rows:
            data = rows[row]
            if op == '=':
                if column in data and data[column] == value:
                    r[row] = data
            elif op == '<':
                if column in data and data[column] < value:
                    r[row] = data
            elif op == '<=':
                if column in data and data[column] <= value:
                    r[row] = data
            elif op == '>':
                if column in data and data[column] > value:
                    r[row] = data
            elif op == '>=':
                if column in data and data[column] >= value:
                    r[row] = data
            elif op == '!=':
                if column in data and data[column] != value:
                    r[row] = data
        return r

    @staticmethod
    def ColumnPrefixFilter(args, rows):
        """This is filter for testing "in-memory HBase".

        This method is called from scan() when 'ColumnPrefixFilter' is found
        in the 'filter' argument.

        :param args: a list of filter arguments, contain prefix of column
        :param rows: a dict of row prefixes for filtering
        """
        value = args[0]
        column = 'f:' + value
        r = {}
        for row, data in rows.items():
            column_dict = {}
            for key in data:
                if key.startswith(column):
                    column_dict[key] = data[key]
            r[row] = column_dict
        return r

    @staticmethod
    def RowFilter(args, rows):
        """This is filter for testing "in-memory HBase".

        This method is called from scan() when 'RowFilter' is found in the
        'filter' argument.

        :param args: a list of filter arguments, it contains operator and
          sought string
        :param rows: a dict of rows which are filtered
        """
        op = args[0]
        value = args[1]
        if value.startswith('regexstring:'):
            value = value[len('regexstring:'):]
        r = {}
        for row, data in rows.items():
            try:
                g = re.search(value, row).group()
                if op == '=':
                    if g == row:
                        r[row] = data
                else:
                    raise ceilometer.NotImplementedError(
                        "In-memory "
                        "RowFilter doesn't support "
                        "the %s operation yet" % op)
            except AttributeError:
                pass
        return r

    @staticmethod
    def QualifierFilter(args, rows):
        """This is filter for testing "in-memory HBase".

        This method is called from scan() when 'QualifierFilter' is found in
        the 'filter' argument
        """
        op = args[0]
        value = args[1]
        is_regex = False
        if value.startswith('binaryprefix:'):
            value = value[len('binaryprefix:'):]
        if value.startswith('regexstring:'):
            value = value[len('regexstring:'):]
            is_regex = True
        column = 'f:' + value
        r = {}
        for row in rows:
            data = rows[row]
            r_data = {}
            for key in data:
                if ((op == '=' and key.startswith(column)) or
                        (op == '>=' and key >= column) or
                        (op == '<=' and key <= column) or
                        (op == '>' and key > column) or
                        (op == '<' and key < column) or
                        (is_regex and re.search(value, key))):
                    r_data[key] = data[key]
                else:
                    raise ceilometer.NotImplementedError(
                        "In-memory QualifierFilter "
                        "doesn't support the %s "
                        "operation yet" % op)
            if r_data:
                r[row] = r_data
        return r


class MConnectionPool(object):
    def __init__(self):
        self.conn = MConnection()

    def connection(self):
        return self.conn


class MConnection(object):
    """HappyBase.Connection mock."""
    def __init__(self):
        self.tables = {}

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def open():
        LOG.debug("Opening in-memory HBase connection")

    def create_table(self, n, families=None):
        families = families or {}
        if n in self.tables:
            return self.tables[n]
        t = MTable(n, families)
        self.tables[n] = t
        return t

    def delete_table(self, name, use_prefix=True):
        del self.tables[name]

    def table(self, name):
        return self.create_table(name)
