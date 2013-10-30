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
SQLAlchemy models for Ceilometer data.
"""

import json
import urlparse

from oslo.config import cfg
from sqlalchemy import Column, Integer, String, Table, ForeignKey, DateTime, \
    Index, UniqueConstraint
from sqlalchemy import Float, Boolean, Text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, DATETIME

from ceilometer.openstack.common import timeutils
from ceilometer.storage import models as api_models
from ceilometer import utils

sql_opts = [
    cfg.StrOpt('mysql_engine',
               default='InnoDB',
               help='MySQL engine')
]

cfg.CONF.register_opts(sql_opts)


def table_args():
    engine_name = urlparse.urlparse(cfg.CONF.database.connection).scheme
    if engine_name == 'mysql':
        return {'mysql_engine': cfg.CONF.mysql_engine,
                'mysql_charset': "utf8"}
    return None


class JSONEncodedDict(TypeDecorator):
    "Represents an immutable structure as a json-encoded string."

    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class PreciseTimestamp(TypeDecorator):
    """Represents a timestamp precise to the microsecond."""

    impl = DATETIME

    def load_dialect_impl(self, dialect):
        if dialect.name == 'mysql':
            return dialect.type_descriptor(DECIMAL(precision=20,
                                                   scale=6,
                                                   asdecimal=True))
        return dialect.type_descriptor(DATETIME())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'mysql':
            return utils.dt_to_decimal(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'mysql':
            return utils.decimal_to_dt(value)
        return value


class CeilometerBase(object):
    """Base class for Ceilometer Models."""
    __table_args__ = table_args()
    __table_initialized__ = False

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def update(self, values):
        """Make the model object behave like a dict."""
        for k, v in values.iteritems():
            setattr(self, k, v)


Base = declarative_base(cls=CeilometerBase)


sourceassoc = Table('sourceassoc', Base.metadata,
                    Column('meter_id', Integer,
                           ForeignKey("meter.id")),
                    Column('project_id', String(255),
                           ForeignKey("project.id")),
                    Column('resource_id', String(255),
                           ForeignKey("resource.id")),
                    Column('user_id', String(255),
                           ForeignKey("user.id")),
                    Column('source_id', String(255),
                           ForeignKey("source.id")))

Index('idx_su', sourceassoc.c['source_id'], sourceassoc.c['user_id']),
Index('idx_sp', sourceassoc.c['source_id'], sourceassoc.c['project_id']),
Index('idx_sr', sourceassoc.c['source_id'], sourceassoc.c['resource_id']),
Index('idx_sm', sourceassoc.c['source_id'], sourceassoc.c['meter_id']),
Index('ix_sourceassoc_source_id', sourceassoc.c['source_id'])
UniqueConstraint(sourceassoc.c['meter_id'], sourceassoc.c['user_id'],
                 name='uniq_sourceassoc0meter_id0user_id')


class Source(Base):
    __tablename__ = 'source'
    id = Column(String(255), primary_key=True)


class MetaText(Base):
    """Metering text metadata."""

    __tablename__ = 'metadata_text'
    __table_args__ = (
        Index('ix_meta_text_key', 'meta_key'),
    )
    id = Column(Integer, ForeignKey('meter.id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(Text)


class MetaBool(Base):
    """Metering boolean metadata."""

    __tablename__ = 'metadata_bool'
    __table_args__ = (
        Index('ix_meta_bool_key', 'meta_key'),
    )
    id = Column(Integer, ForeignKey('meter.id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(Boolean)


class MetaInt(Base):
    """Metering integer metadata."""

    __tablename__ = 'metadata_int'
    __table_args__ = (
        Index('ix_meta_int_key', 'meta_key'),
    )
    id = Column(Integer, ForeignKey('meter.id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(Integer, default=False)


class MetaFloat(Base):
    """Metering float metadata."""

    __tablename__ = 'metadata_float'
    __table_args__ = (
        Index('ix_meta_float_key', 'meta_key'),
    )
    id = Column(Integer, ForeignKey('meter.id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(Float, default=False)


class Meter(Base):
    """Metering data."""

    __tablename__ = 'meter'
    __table_args__ = (
        Index('ix_meter_timestamp', 'timestamp'),
        Index('ix_meter_user_id', 'user_id'),
        Index('ix_meter_project_id', 'project_id'),
        Index('idx_meter_rid_cname', 'resource_id', 'counter_name'),
    )
    id = Column(Integer, primary_key=True)
    counter_name = Column(String(255))
    sources = relationship("Source", secondary=lambda: sourceassoc)
    user_id = Column(String(255), ForeignKey('user.id'))
    project_id = Column(String(255), ForeignKey('project.id'))
    resource_id = Column(String(255), ForeignKey('resource.id'))
    resource_metadata = Column(JSONEncodedDict())
    counter_type = Column(String(255))
    counter_unit = Column(String(255))
    counter_volume = Column(Float(53))
    timestamp = Column(PreciseTimestamp(), default=timeutils.utcnow)
    message_signature = Column(String(1000))
    message_id = Column(String(1000))


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
    __table_args__ = (
        Index('ix_resource_project_id', 'project_id'),
        Index('ix_resource_user_id', 'user_id'),
        Index('resource_user_id_project_id_key', 'user_id', 'project_id')
    )
    id = Column(String(255), primary_key=True)
    sources = relationship("Source", secondary=lambda: sourceassoc)
    resource_metadata = Column(JSONEncodedDict())
    user_id = Column(String(255), ForeignKey('user.id'))
    project_id = Column(String(255), ForeignKey('project.id'))
    meters = relationship("Meter", backref='resource')


class Alarm(Base):
    """Define Alarm data."""
    __tablename__ = 'alarm'
    __table_args__ = (
        Index('ix_alarm_user_id', 'user_id'),
        Index('ix_alarm_project_id', 'project_id'),
    )
    id = Column(String(255), primary_key=True)
    enabled = Column(Boolean)
    name = Column(Text)
    type = Column(String(50))
    description = Column(Text)
    timestamp = Column(DateTime, default=timeutils.utcnow)

    user_id = Column(String(255), ForeignKey('user.id'))
    project_id = Column(String(255), ForeignKey('project.id'))

    state = Column(String(255))
    state_timestamp = Column(DateTime, default=timeutils.utcnow)

    ok_actions = Column(JSONEncodedDict)
    alarm_actions = Column(JSONEncodedDict)
    insufficient_data_actions = Column(JSONEncodedDict)
    repeat_actions = Column(Boolean)

    rule = Column(JSONEncodedDict)


class AlarmChange(Base):
    """Define AlarmChange data."""
    __tablename__ = 'alarm_history'
    __table_args__ = (
        Index('ix_alarm_history_alarm_id', 'alarm_id'),
    )
    event_id = Column(String(255), primary_key=True)
    alarm_id = Column(String(255))
    on_behalf_of = Column(String(255), ForeignKey('project.id'))
    project_id = Column(String(255), ForeignKey('project.id'))
    user_id = Column(String(255), ForeignKey('user.id'))
    type = Column(String(20))
    detail = Column(Text)
    timestamp = Column(DateTime, default=timeutils.utcnow)


class UniqueName(Base):
    """Key names should only be stored once.
    """
    __tablename__ = 'unique_name'
    __table_args__ = (
        Index('ix_unique_name_key', 'key'),
    )

    id = Column(Integer, primary_key=True)
    key = Column(String(255))

    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return "<UniqueName: %s>" % self.key


class Event(Base):
    __tablename__ = 'event'
    __table_args__ = (
        Index('unique_name_id', 'unique_name_id'),
        Index('ix_event_message_id', 'message_id'),
        Index('ix_event_generated', 'generated'),
    )
    id = Column(Integer, primary_key=True)
    message_id = Column(String(50), unique=True)
    generated = Column(Float(asdecimal=True))

    unique_name_id = Column(Integer, ForeignKey('unique_name.id'))
    unique_name = relationship("UniqueName", backref=backref('unique_name',
                               order_by=id))

    def __init__(self, message_id, event, generated):
        self.message_id = message_id
        self.unique_name = event
        self.generated = generated

    def __repr__(self):
        return "<Event %d('Event: %s %s, Generated: %s')>" % \
               (self.id, self.message_id, self.unique_name, self.generated)


class Trait(Base):
    __tablename__ = 'trait'
    __table_args__ = (
        Index('ix_trait_t_int', 't_int'),
        Index('ix_trait_t_string', 't_string'),
        Index('ix_trait_t_datetime', 't_datetime'),
        Index('ix_trait_t_type', 't_type'),
        Index('ix_trait_t_float', 't_float'),
    )
    id = Column(Integer, primary_key=True)

    name_id = Column(Integer, ForeignKey('unique_name.id'))
    name = relationship("UniqueName", backref=backref('name', order_by=id))

    t_type = Column(Integer)
    t_string = Column(String(255), nullable=True, default=None)
    t_float = Column(Float, nullable=True, default=None)
    t_int = Column(Integer, nullable=True, default=None)
    t_datetime = Column(Float(asdecimal=True), nullable=True, default=None)

    event_id = Column(Integer, ForeignKey('event.id'))
    event = relationship("Event", backref=backref('event', order_by=id))

    _value_map = {api_models.Trait.TEXT_TYPE: 't_string',
                  api_models.Trait.FLOAT_TYPE: 't_float',
                  api_models.Trait.INT_TYPE: 't_int',
                  api_models.Trait.DATETIME_TYPE: 't_datetime'}

    def __init__(self, name, event, t_type, t_string=None, t_float=None,
                 t_int=None, t_datetime=None):
        self.name = name
        self.t_type = t_type
        self.t_string = t_string
        self.t_float = t_float
        self.t_int = t_int
        self.t_datetime = t_datetime
        self.event = event

    def get_value(self):
        if self.t_type == api_models.Trait.INT_TYPE:
            return self.t_int
        if self.t_type == api_models.Trait.FLOAT_TYPE:
            return self.t_float
        if self.t_type == api_models.Trait.DATETIME_TYPE:
            return utils.decimal_to_dt(self.t_datetime)
        if self.t_type == api_models.Trait.TEXT_TYPE:
            return self.t_string
        return None

    def __repr__(self):
        return "<Trait(%s) %d=%s/%s/%s/%s on %s>" % (self.name, self.t_type,
               self.t_string, self.t_float, self.t_int, self.t_datetime,
               self.event)
