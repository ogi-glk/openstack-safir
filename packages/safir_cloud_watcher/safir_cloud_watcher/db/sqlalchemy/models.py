# Copyright 2024 TUBITAK.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_db.sqlalchemy import models
from oslo_utils import timeutils
from sqlalchemy import (Column, DateTime, JSON, Integer, String,
                        schema)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import orm


BASE = declarative_base()


class SafirCloudWatcherTimestampMixin(object):
    # Note(tpatil): timeutils.utcnow() method return microseconds part but db
    # doesn't store it because of which subsequent calls to get resources
    # from the same db session object instance doesn't return microsecond for
    # datetime fields. To avoid this discrepancy, removed microseconds from
    # datetime fields so that there is no need to remove it for create/update
    # cases in the respective versioned objects.
    created_at = Column(DateTime, default=lambda: timeutils.utcnow().replace(
                        microsecond=0))
    updated_at = Column(DateTime, onupdate=lambda: timeutils.utcnow().replace(
                        microsecond=0))


class SafirCloudWatcherAPIBase(SafirCloudWatcherTimestampMixin, models.ModelBase):
    """Base class for SafirCloudWatcherAPIBase Models."""

    metadata = None

    def __copy__(self):
        """Implement a safe copy.copy().

        SQLAlchemy-mapped objects travel with an object
        called an InstanceState, which is pegged to that object
        specifically and tracks everything about that object.  It's
        critical within all attribute operations, including gets
        and deferred loading.   This object definitely cannot be
        shared among two instances, and must be handled.

        The copy routine here makes use of session.merge() which
        already essentially implements a "copy" style of operation,
        which produces a new instance with a new InstanceState and copies
        all the data along mapped attributes without using any SQL.

        The mode we are using here has the caveat that the given object
        must be "clean", e.g. that it has no database-loaded state
        that has been updated and not flushed.   This is a good thing,
        as creating a copy of an object including non-flushed, pending
        database state is probably not a good idea; neither represents
        what the actual row looks like, and only one should be flushed.

        """
        session = orm.Session()

        copy = session.merge(self, load=False)
        session.expunge(copy)
        return copy


class LicenceInfo(BASE, SafirCloudWatcherAPIBase, models.SoftDeleteMixin):
    """Represents a host."""
    __tablename__ = 'licence'
    __table_args__ = (
        schema.UniqueConstraint("id", "deleted",
                                name="uniq_licence0id0deleted"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    licence_key = Column(String(length=255), nullable=False)
    notification_address = Column(String(length=255), nullable=True)
    notification_counter = Column(String(length=255), nullable=False)
    last_notification_time = Column(String(length=255), nullable=True)

    def __repr__(self):
        return ('<LicenceInfo[{id}]: '
                'licence_key={licence_key}'
                'notification_address={notification_address}'
                'notification_counter={notification_counter}'
                'last_notification_time={last_notification_time}>').format(
            id=self.id,
            licence_key=self.licence_key,
            notification_address=self.notification_address,
            notification_counter=self.notification_counter,
            last_notification_time=self.last_notification_time)

    def as_dict(self):
        d = {}
        for c in self.__table__.columns:
            d[c.name] = self[c.name]
        return d
