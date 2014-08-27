# Author: John Tran <jhtran@att.com>
#         Julien Danjou <julien@danjou.info>
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
#

import operator
import types

from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import not_
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from ceilometer.storage.sqlalchemy import models


META_TYPE_MAP = {bool: models.MetaBool,
                 str: models.MetaText,
                 unicode: models.MetaText,
                 types.NoneType: models.MetaText,
                 int: models.MetaBigInt,
                 long: models.MetaBigInt,
                 float: models.MetaFloat}


class QueryTransformer(object):
    operators = {"=": operator.eq,
                 "<": operator.lt,
                 ">": operator.gt,
                 "<=": operator.le,
                 "=<": operator.le,
                 ">=": operator.ge,
                 "=>": operator.ge,
                 "!=": operator.ne,
                 "in": lambda field_name, values: field_name.in_(values)}

    complex_operators = {"or": or_,
                         "and": and_,
                         "not": not_}

    ordering_functions = {"asc": asc,
                          "desc": desc}

    def __init__(self, table, query):
        self.table = table
        self.query = query

    def _handle_complex_op(self, complex_op, nodes):
        op = self.complex_operators[complex_op]
        if op == not_:
            nodes = [nodes]
        element_list = []
        for node in nodes:
            element = self._transform(node)
            element_list.append(element)
        return op(*element_list)

    def _handle_simple_op(self, simple_op, nodes):
        op = self.operators[simple_op]
        field_name = nodes.keys()[0]
        value = nodes.values()[0]
        if field_name.startswith('resource_metadata.'):
            return self._handle_metadata(op, field_name, value)
        else:
            return op(getattr(self.table, field_name), value)

    def _handle_metadata(self, op, field_name, value):
        if op == self.operators["in"]:
            raise NotImplementedError('Metadata query with in '
                                      'operator is not implemented')

        field_name = field_name[len('resource_metadata.'):]
        meta_table = META_TYPE_MAP[type(value)]
        meta_alias = aliased(meta_table)
        on_clause = and_(self.table.id == meta_alias.id,
                         meta_alias.meta_key == field_name)
        # outer join is needed to support metaquery
        # with or operator on non existent metadata field
        # see: test_query_non_existing_metadata_with_result
        # test case.
        self.query = self.query.outerjoin(meta_alias, on_clause)
        return op(meta_alias.value, value)

    def _transform(self, sub_tree):
        operator = sub_tree.keys()[0]
        nodes = sub_tree.values()[0]
        if operator in self.complex_operators:
            return self._handle_complex_op(operator, nodes)
        else:
            return self._handle_simple_op(operator, nodes)

    def apply_filter(self, expression_tree):
        condition = self._transform(expression_tree)
        self.query = self.query.filter(condition)

    def apply_options(self, orderby, limit):
        self._apply_order_by(orderby)
        if limit is not None:
            self.query = self.query.limit(limit)

    def _apply_order_by(self, orderby):
        if orderby is not None:
            for field in orderby:
                ordering_function = self.ordering_functions[field.values()[0]]
                self.query = self.query.order_by(ordering_function(
                    getattr(self.table, field.keys()[0])))
        else:
            self.query = self.query.order_by(desc(self.table.timestamp))

    def get_query(self):
        return self.query


trait_models_dict = {'string': models.Trait.t_string,
                     'integer': models.Trait.t_int,
                     'datetime': models.Trait.t_datetime,
                     'float': models.Trait.t_float}


def trait_op_condition(conditions, trait_type, value, op='eq'):
    trait_model = trait_models_dict[trait_type]
    op_dict = {'eq': (trait_model == value), 'lt': (trait_model < value),
               'le': (trait_model <= value), 'gt': (trait_model > value),
               'ge': (trait_model >= value), 'ne': (trait_model != value)}
    conditions.append(op_dict[op])
    return conditions
