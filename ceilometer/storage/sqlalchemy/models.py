# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
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

"""
SQLAlchemy models for nova data.
"""

import json
from sqlalchemy import Column, Integer, String, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.types import TypeDecorator, VARCHAR
from urlparse import urlparse

import ceilometer.openstack.common.cfg as cfg
from ceilometer.openstack.common import timeutils

sql_opts = [
    cfg.IntOpt('mysql_engine',
               default='InnoDB',
               help='MySQL engine')
           ]

cfg.CONF.register_opts(sql_opts)


def table_args():
    engine_name = urlparse(cfg.CONF.database_connection).scheme
    if engine_name == 'mysql':
        return {'mysql_engine': cfg.CONF.mysql_engine}
    return None


class JSONEncodedDict(TypeDecorator):
    "Represents an immutable structure as a json-encoded string."

    impl = VARCHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class CeilometerBase(object):
    """Base class for Ceilometer Models."""
    __table_args__ = table_args()
    __table_initialized__ = False

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)


Base = declarative_base(cls=CeilometerBase)


sourceassoc = Table('sourceassoc', Base.metadata,
    Column('meter_id', Integer, ForeignKey("meter.id")),
    Column('project_id', String(255), ForeignKey("project.id")),
    Column('resource_id', String(255), ForeignKey("resource.id")),
    Column('user_id', String(255), ForeignKey("user.id")),
    Column('source_id', String(255), ForeignKey("source.id"))
)


class Source(Base):
    __tablename__ = 'source'
    id = Column(String(255), primary_key=True)


class Meter(Base):
    """Metering data"""

    __tablename__ = 'meter'
    id = Column(Integer, primary_key=True)
    counter_name = Column(String(255))
    sources = relationship("Source", secondary=lambda: sourceassoc)
    user_id = Column(String(255), ForeignKey('user.id'))
    project_id = Column(String(255), ForeignKey('project.id'))
    resource_id = Column(String(255), ForeignKey('resource.id'))
    resource_metadata = Column(JSONEncodedDict)
    counter_type = Column(String(255))
    counter_volume = Column(Integer)
    timestamp = Column(DateTime, default=timeutils.utcnow)
    message_signature = Column(String)
    message_id = Column(String)


class User(Base):
    __tablename__ = 'user'
    id = Column(String(255), primary_key=True)
    sources = relationship("Source", secondary=lambda: sourceassoc)
    resources = relationship("Resource", backref='user')
    meters = relationship("Meter", backref='user')


class Project(Base):
    __tablename__ = 'project'
    id = Column(String(255), primary_key=True)
    sources = relationship("Source", secondary=lambda: sourceassoc)
    resources = relationship("Resource", backref='project')
    meters = relationship("Meter", backref='project')


class Resource(Base):
    __tablename__ = 'resource'
    id = Column(String(255), primary_key=True)
    sources = relationship("Source", secondary=lambda: sourceassoc)
    timestamp = Column(DateTime)
    resource_metadata = Column(JSONEncodedDict)
    received_timestamp = Column(DateTime, default=timeutils.utcnow)
    user_id = Column(String(255), ForeignKey('user.id'))
    project_id = Column(String(255), ForeignKey('project.id'))
    meters = relationship("Meter", backref='resource')
