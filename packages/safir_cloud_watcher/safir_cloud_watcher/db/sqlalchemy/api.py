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
"""Implementation of SQLAlchemy backend."""

import datetime
import functools
import sys

from oslo_db import api as oslo_db_api
from oslo_db.sqlalchemy import enginefacade
from oslo_db.sqlalchemy import utils as sqlalchemyutils
from oslo_log import log as logging
from oslo_utils import timeutils
import sqlalchemy as sa
from sqlalchemy import MetaData
from sqlalchemy import sql
import sqlalchemy.sql as sa_sql

from oslo_config import cfg
from safir_cloud_watcher.db.sqlalchemy import models
from safir_cloud_watcher.i18n import _

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

main_context_manager = enginefacade.transaction_context()


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


def _get_db_conf(conf_group, connection=None):
    kw = dict(conf_group.items())
    if connection is not None:
        kw['connection'] = connection
    return kw


def configure(conf):
    main_context_manager.configure(**_get_db_conf(conf.database))


def get_engine(use_slave=False):
    """Get a database engine object.

    :param use_slave: Whether to use the slave connection
    """
    return main_context_manager.get_legacy_facade().get_engine(use_slave=use_slave)


def get_session():
    """Get a database engine object."""
    return main_context_manager.get_legacy_facade().get_session()


def model_query(context, model, args=None, read_deleted=None):
    """Query helper that accounts for context's `read_deleted` field.
    :param context:     MasakariContext of the query.
    :param model:       Model to query. Must be a subclass of ModelBase.
    :param args:        Arguments to query. If None - model is used.
    :param read_deleted: If not None, overrides context's read_deleted field.
                        Permitted values are 'no', which does not return
                        deleted values; 'only', which only returns deleted
                        values; and 'yes', which does not filter deleted
                        values.
    """
    if read_deleted is None:
        read_deleted = context.read_deleted

    query_kwargs = {}
    if read_deleted is None or 'no' == read_deleted:
        query_kwargs['deleted'] = False
    elif 'only' == read_deleted:
        query_kwargs['deleted'] = True
    elif 'yes' == read_deleted:
        pass
    else:
        raise ValueError(_("Unrecognized read_deleted value '%s'")
                         % read_deleted)

    query = sqlalchemyutils.model_query(
        model, context.session, args, **query_kwargs)

    return query


def log_call(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        LOG.info(_('Calling %(funcname)s: args=%(args)s, '
                   'kwargs=%(kwargs)s'),
                 {"funcname": f.__name__,
                  "args": args,
                  "kwargs": kwargs})
        output = f(*args, **kwargs)
        LOG.info(_('Returning %(funcname)s: %(output)s'),
                 {"funcname": f.__name__,
                  "output": output})
        return output
    return wrapped


class LicenceNotFound(Exception):
    """
    Raised when the licence doesn't exist.
    """

    def __init__(self):
        super(LicenceNotFound, self).__init__(
            "Licence not found")
# db apis for licence


@log_call
@oslo_db_api.wrap_db_retry(max_retries=5, retry_on_deadlock=True)
@main_context_manager.reader
def get_licence(context):
    query = model_query(
        context,
        models.LicenceInfo,
    )
    result = query.first()
    if not result:
        raise LicenceNotFound()

    return result


@log_call
@oslo_db_api.wrap_db_retry(max_retries=5, retry_on_deadlock=True)
@main_context_manager.writer
def set_licence(context, values):
    try:
        licence = get_licence(context)
    except LicenceNotFound:
        licence = models.LicenceInfo()

    licence.update(values)
    licence.save(session=context.session)

    return get_licence(context)


@log_call
@oslo_db_api.wrap_db_retry(max_retries=5, retry_on_deadlock=True)
@main_context_manager.writer
def delete_licence(context):
    count = model_query(context, models.LicenceInfo
                        ).soft_delete(synchronize_session=False)

    if count == 0:
        raise LicenceNotFound()


class DeleteFromSelect(sa_sql.expression.UpdateBase):
    inherit_cache = False

    def __init__(self, table, select, column):
        self.table = table
        self.select = select
        self.column = column

@log_call
@oslo_db_api.wrap_db_retry(max_retries=5, retry_on_deadlock=True)
@main_context_manager.writer
def purge_deleted_rows(age_in_days, max_rows):
    """Purges soft deleted rows

    Deleted rows get purged from clusters and segment tables based on
    deleted_at column. As notifications table doesn't delete any of
    the notification records so rows get purged from notifications
    based on last updated_at and status column.
    """
    engine = get_engine()
    metadata = MetaData()
    metadata.reflect(engine)
    deleted_age = timeutils.utcnow() - datetime.timedelta(days=age_in_days)
    total_rows_purged = 0
    for table in reversed(metadata.sorted_tables):
        if 'deleted' not in table.columns.keys():
            continue
        LOG.info('Purging deleted rows older than %(age_in_days)d day(s) '
                 'from table %(tbl)s',
            {'age_in_days': age_in_days, 'tbl': table})
        column = table.c.id
        updated_at_column = table.c.updated_at
        deleted_at_column = table.c.deleted_at

        if table.name == 'notifications':
            status_column = table.c.status
            query_delete = sql.select(column).where(
                sa.and_(
                    updated_at_column < deleted_age,
                    sa.or_(
                        status_column == 'finished',
                        status_column == 'failed',
                        status_column == 'ignored',
                    ),
                ),
            ).order_by(status_column)
        else:
            query_delete = sql.select(
                column,
            ).where(
                deleted_at_column < deleted_age,
            ).order_by(
                deleted_at_column,
            )

        if max_rows > 0:
            query_delete = query_delete.limit(max_rows - total_rows_purged)

        delete_statement = DeleteFromSelect(table, query_delete, column)

        with engine.connect() as conn, conn.begin():
            result = conn.execute(delete_statement)

        rows = result.rowcount
        LOG.info('Deleted %(rows)d row(s) from table %(tbl)s',
                 {'rows': rows, 'tbl': table})

        total_rows_purged += rows
        if max_rows > 0 and total_rows_purged == max_rows:
            break

    LOG.info('Total deleted rows are %(rows)d', {'rows': total_rows_purged})
