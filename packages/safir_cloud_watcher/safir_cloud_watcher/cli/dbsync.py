# -*- coding: utf-8 -*-
# Copyright 2014 Objectif Libre
# Copyright 2021 TUBITAK B3LAB
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

import sys
import time

from oslo_config import cfg
from oslo_utils import strutils

from safir_cloud_watcher import config  # noqa
from safir_cloud_watcher import service
from safir_cloud_watcher import context
from safir_cloud_watcher.db import api as db_api
from safir_cloud_watcher.db.sqlalchemy import migration as db_migration
from safir_cloud_watcher.i18n import _

CONF = cfg.CONF
PROCESSORS_NAMESPACE = 'safir_cloud_watcher.watcher.processors'


class ModuleNotFound(Exception):
    def __init__(self, name):
        self.name = name
        super(ModuleNotFound, self).__init__(
            "Module %s not found" % name)


class MultipleModulesRevisions(Exception):
    def __init__(self, revision):
        self.revision = revision
        super(MultipleModulesRevisions, self).__init__(
            "Can't apply revision %s to multiple modules." % revision)


class DBCommand(object):

    def __init__(self):
        pass

    def upgrade(self, version=None):
        """Sync the database up to the most recent version."""
        try:
            return db_migration.db_sync(version)
        except Exception as ex:
            print(ex)
            sys.exit(1)

    def version(self):
        """Print the current database version."""
        print(db_migration.db_version())

    def purge(self, age_in_days, max_rows):
        """Purge rows older than a given age from safir_api_gateway tables."""
        try:
            max_rows = strutils.validate_integer(
                max_rows, 'max_rows', -1, db_api.MAX_INT)
        except Exception as exc:
            sys.exit(str(exc))

        try:
            age_in_days = int(age_in_days)
        except ValueError:
            msg = 'Invalid value for age, %(age)s' % {'age': age_in_days}
            sys.exit(str(msg))

        if max_rows == 0:
            sys.exit(_("Must supply value greater than 0 for max_rows."))
        if age_in_days < 0:
            sys.exit(_("Must supply a non-negative value for age."))
        if age_in_days >= (int(time.time()) / 86400):
            sys.exit(_("Maximal age is count of days since epoch."))

        ctx = context.get_admin_context()
        db_api.purge_deleted_rows(ctx, age_in_days, max_rows)


def add_command_parsers(subparsers):
    command_object = DBCommand()

    parser = subparsers.add_parser('upgrade')
    parser.set_defaults(func=command_object.upgrade)
    parser.add_argument('--version', nargs='?')

    parser = subparsers.add_parser('version')
    parser.set_defaults(func=command_object.version)

    parser = subparsers.add_parser('purge')
    parser.set_defaults(func=command_object.version)
    parser.add_argument('--age_in_days', nargs='?', type=int, default=30,
                        help='Purge deleted rows older than age in days (default: '
                             '%(default)d)')
    parser.add_argument('--max_rows', nargs='?', type=int, default=-1,
                        help='Limit number of records to delete (default: %(default)d)')


command_opt = cfg.SubCommandOpt('command',
                                title='Command',
                                help='Available commands',
                                handler=add_command_parsers)

CONF.register_cli_opt(command_opt)


def main():
    service.prepare_service()
    CONF.command.func()
