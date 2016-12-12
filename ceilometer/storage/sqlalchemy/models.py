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
import hashlib
import json

from oslo_utils import timeutils
import six
from sqlalchemy import (Column, Integer, String, ForeignKey, Index,
                        UniqueConstraint, BigInteger)
from sqlalchemy import event
from sqlalchemy import Float, Boolean, Text, DateTime
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import deferred
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator

from ceilometer import utils


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""

    impl = Text

    @staticmethod
    def process_bind_param(value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    @staticmethod
    def process_result_value(value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class PreciseTimestamp(TypeDecorator):
    """Represents a timestamp precise to the microsecond."""

    impl = DateTime

    def load_dialect_impl(self, dialect):
        if dialect.name == 'mysql':
            return dialect.type_descriptor(DECIMAL(precision=20,
                                                   scale=6,
                                                   asdecimal=True))
        return self.impl

    @staticmethod
    def process_bind_param(value, dialect):
        if value is None:
            return value
        elif dialect.name == 'mysql':
            return utils.dt_to_decimal(value)
        return value

    @staticmethod
    def process_result_value(value, dialect):
        if value is None:
            return value
        elif dialect.name == 'mysql':
            return utils.decimal_to_dt(value)
        return value


_COMMON_TABLE_ARGS = {'mysql_charset': "utf8", 'mysql_engine': "InnoDB"}


class CeilometerBase(object):
    """Base class for Ceilometer Models."""
    __table_args__ = _COMMON_TABLE_ARGS
    __table_initialized__ = False

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def update(self, values):
        """Make the model object behave like a dict."""
        for k, v in six.iteritems(values):
            setattr(self, k, v)


Base = declarative_base(cls=CeilometerBase)


class MetaText(Base):
    """Metering text metadata."""

    __tablename__ = 'metadata_text'
    __table_args__ = (
        Index('ix_meta_text_key', 'meta_key'),
        _COMMON_TABLE_ARGS,
    )
    id = Column(Integer, ForeignKey('resource.internal_id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(Text)


class MetaBool(Base):
    """Metering boolean metadata."""

    __tablename__ = 'metadata_bool'
    __table_args__ = (
        Index('ix_meta_bool_key', 'meta_key'),
        _COMMON_TABLE_ARGS,
    )
    id = Column(Integer, ForeignKey('resource.internal_id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(Boolean)


class MetaBigInt(Base):
    """Metering integer metadata."""

    __tablename__ = 'metadata_int'
    __table_args__ = (
        Index('ix_meta_int_key', 'meta_key'),
        _COMMON_TABLE_ARGS,
    )
    id = Column(Integer, ForeignKey('resource.internal_id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(BigInteger, default=False)


class MetaFloat(Base):
    """Metering float metadata."""

    __tablename__ = 'metadata_float'
    __table_args__ = (
        Index('ix_meta_float_key', 'meta_key'),
        _COMMON_TABLE_ARGS,
    )
    id = Column(Integer, ForeignKey('resource.internal_id'), primary_key=True)
    meta_key = Column(String(255), primary_key=True)
    value = Column(Float(53), default=False)


class Meter(Base):
    """Meter definition data."""

    __tablename__ = 'meter'
    __table_args__ = (
        UniqueConstraint('name', 'type', 'unit', name='def_unique'),
        Index('ix_meter_name', 'name'),
        _COMMON_TABLE_ARGS,
    )
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    type = Column(String(255))
    unit = Column(String(255))
    samples = relationship("Sample", backref="meter")


class Resource(Base):
    """Resource data."""

    __tablename__ = 'resource'
    __table_args__ = (
        # TODO(gordc): this should exist but the attribute values we set
        #              for user/project/source/resource id's are too large
        #              for an uuid.
        # UniqueConstraint('resource_id', 'user_id', 'project_id',
        #                  'source_id', 'metadata_hash',
        #                  name='res_def_unique'),
        Index('ix_resource_resource_id', 'resource_id'),
        Index('ix_resource_metadata_hash', 'metadata_hash'),
        _COMMON_TABLE_ARGS,
    )

    internal_id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    project_id = Column(String(255))
    source_id = Column(String(255))
    resource_id = Column(String(255), nullable=False)
    resource_metadata = deferred(Column(JSONEncodedDict()))
    metadata_hash = deferred(Column(String(32)))
    samples = relationship("Sample", backref="resource")
    meta_text = relationship("MetaText", backref="resource",
                             cascade="all, delete-orphan")
    meta_float = relationship("MetaFloat", backref="resource",
                              cascade="all, delete-orphan")
    meta_int = relationship("MetaBigInt", backref="resource",
                            cascade="all, delete-orphan")
    meta_bool = relationship("MetaBool", backref="resource",
                             cascade="all, delete-orphan")


@event.listens_for(Resource, "before_insert")
def before_insert(mapper, connection, target):
    metadata = json.dumps(target.resource_metadata, sort_keys=True)
    target.metadata_hash = hashlib.md5(metadata).hexdigest()


class Sample(Base):
    """Metering data."""

    __tablename__ = 'sample'
    __table_args__ = (
        Index('ix_sample_timestamp', 'timestamp'),
        Index('ix_sample_resource_id', 'resource_id'),
        Index('ix_sample_meter_id', 'meter_id'),
        Index('ix_sample_meter_id_resource_id', 'meter_id', 'resource_id'),
        _COMMON_TABLE_ARGS,
    )
    id = Column(Integer, primary_key=True)
    meter_id = Column(Integer, ForeignKey('meter.id'))
    resource_id = Column(Integer, ForeignKey('resource.internal_id'))
    volume = Column(Float(53))
    timestamp = Column(PreciseTimestamp(), default=lambda: timeutils.utcnow())
    recorded_at = Column(PreciseTimestamp(),
                         default=lambda: timeutils.utcnow())
    message_signature = Column(String(64))
    message_id = Column(String(128))


class FullSample(object):
    """A fake model for query samples."""
    id = Sample.id
    timestamp = Sample.timestamp
    message_id = Sample.message_id
    message_signature = Sample.message_signature
    recorded_at = Sample.recorded_at
    counter_name = Meter.name
    counter_type = Meter.type
    counter_unit = Meter.unit
    counter_volume = Sample.volume
    resource_id = Resource.resource_id
    source_id = Resource.source_id
    user_id = Resource.user_id
    project_id = Resource.project_id
    resource_metadata = Resource.resource_metadata
    internal_id = Resource.internal_id
