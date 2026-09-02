# Copyright 2021 99cloud
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from contextvars import ContextVar

from databases import Database, DatabaseURL

from oslo_log import log as logging
from oslo_config import cfg

LOG = logging.getLogger(__name__)

db_opts = [
    cfg.StrOpt('connection',
               default="mysql://safir_monitoring:admin@10.13.0.10:3306/safir_monitoring?charset=utf8",
               help="Database URL"
               ),
    cfg.BoolOpt('db_debug',
                default=True,
                help="LOG level"
                ),
]

CONF = cfg.CONF
CONF.register_opts(db_opts, group='database')


DATABASE = None
DB: ContextVar = ContextVar("safir_monitoring")


class ParallelDatabase(Database):
    pass


async def setup():
    db_url = DatabaseURL(CONF.database.connection)
    print(db_url)
    global DATABASE
    if db_url.scheme in ("mysql", "mysql+pymysql", "mysql+aiomysql"):
        DATABASE = ParallelDatabase(
            db_url,
            minsize=1,
            maxsize=100,
            echo=CONF.database.db_debug,
            charset="utf8",
            client_flag=0,
        )
    elif db_url.scheme == "sqlite":
        DATABASE = ParallelDatabase(db_url)
    else:
        raise ValueError("Unsupported database backend")
    await DATABASE.connect()


async def inject_db():
    global DATABASE
    DB.set(DATABASE)