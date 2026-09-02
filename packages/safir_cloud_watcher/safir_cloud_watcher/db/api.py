# Copyright 2024 TUBITAK
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

from oslo_db import api as db_api
from oslo_config import cfg


_BACKEND_MAPPING = {'sqlalchemy': 'safir_cloud_watcher.db.sqlalchemy.api'}
IMPL = db_api.DBAPI.from_config(cfg.CONF,
                                backend_mapping=_BACKEND_MAPPING,
                                lazy=True)


# The maximum value a signed INT type may have
MAX_INT = 0x7FFFFFFF


def get_engine():
    """Returns database engine"""
    return IMPL.get_engine()


# db apis for licence


def get_licence(context):
    return IMPL.get_licence(context)


def set_licence(context, values):
    return IMPL.set_licence(context, values)


def delete_licence(context):
    return IMPL.delete_licence(context)


def purge_deleted_rows(context, age_in_days, max_rows):
    """Purge the soft deleted rows.

    :param context: context to query under
    :param age_in_days: Purge deleted rows older than age in days
    :param max_rows: Limit number of records to delete
    """
    return IMPL.purge_deleted_rows(context, age_in_days, max_rows)
