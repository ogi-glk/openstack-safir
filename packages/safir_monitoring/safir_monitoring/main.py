# Copyright 2014 IBM Corp
# (C) Copyright 2015,2016 Hewlett Packard Enterprise Development LP
# Copyright 2017 Fujitsu LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import annotations

import os
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from oslo_config import cfg
from oslo_log import log as logging
import paste.deploy

from safir_monitoring.api.v1 import api_router
from safir_monitoring.db import setup as db_setup
from safir_monitoring.types_ import constants
from safir_monitoring import service

LOG = logging.getLogger(__name__)

api_server_opts = [
    cfg.StrOpt('host',
               help="API Host"
               ),
    cfg.IntOpt('port',
               default=9768,
               help="API Port"
               ),
    cfg.StrOpt('log_level',
               default='debug',
               help="API Log Level"
               ),
    cfg.IntOpt('workers',
               default=5,
               help="Uvicorn Worker Count"
               ),
]

common_opts = [
    cfg.StrOpt('config_base_path',
               help='Configuration directory'),

    cfg.StrOpt('config_path',
               help='Configuration path'),
]

opensearch_opts = [
    cfg.StrOpt('url',
               default='https://*.*.*.*:9200',
               help="OpenSearch base URL (e.g. https://host:9200)"),
    cfg.StrOpt('username',
               help="OpenSearch username"),
    cfg.StrOpt('password',
               help="OpenSearch password",
               secret=True),
]

email_notifier_opts = [
    cfg.StrOpt('smtp_host',
               help="SMTP server in host:port format (e.g. mta.example.com:587)"),
    cfg.StrOpt('smtp_from',
               help="Sender address for notification emails"),
    cfg.StrOpt('smtp_user',
               help="SMTP login username"),
    cfg.StrOpt('smtp_pass',
               help="SMTP login password",
               secret=True),
]

thanos_opts = [
    cfg.StrOpt('querier_endpoint',
               default='http://*.*.*.*:10903',
               help="Thanos Querier endpoint URL"),
    cfg.StrOpt('rules_dir',
               default='/var/lib/thanos/rules',
               help="NFS shared directory for Thanos ruler rule files"),
]

CONF = cfg.CONF
CONF.register_opts(common_opts)
CONF.register_opts(api_server_opts, group='api_server')
CONF.register_opts(opensearch_opts, group='opensearch')
CONF.register_opts(email_notifier_opts, group='email_notifier')
CONF.register_opts(thanos_opts, group='thanos')

PROJECT_NAME = "Safir Cloud Service Base FastAPI"


async def on_startup() -> None:
    LOG.debug("Service start")
    await db_setup()

    # APScheduler baslatr ve DB'deki rapor zamanlamalarini yukle
    try:
        from safir_monitoring.reporting.scheduler import get_scheduler, load_schedules_from_db
        scheduler = get_scheduler()
        await load_schedules_from_db()
        if not scheduler.running:
            scheduler.start()
        LOG.info("Report scheduler started")
    except Exception as e:
        LOG.warning(f"Failed to start report scheduler: {e}")


async def on_shutdown() -> None:
    LOG.debug("Service stop")
    try:
        from safir_monitoring.reporting.scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception:
        pass


def app_factory(global_config, **local_conf):

    app = FastAPI(
        title=PROJECT_NAME,
        openapi_url=f"{constants.API_PREFIX}/openapi.json",
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
    )

    app.include_router(api_router, prefix=constants.API_PREFIX)

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version="1.0.0",
            routes=app.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "X-Auth-Token": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Auth-Token",
            }
        }
        openapi_schema["security"] = [{"X-Auth-Token": []}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    @app.get("/healthcheck")
    async def healthcheck():
        return {"status": "ok"}

    @app.get("/debug/auth")
    async def debug_auth(request: Request):
        from safir_monitoring.common import utils
        all_headers = []
        for k, v in request.scope.get('headers', []):
            key = k.decode('latin-1') if isinstance(k, bytes) else k
            val = v.decode('latin-1') if isinstance(v, bytes) else (str(v) if v is not None else 'None')
            all_headers.append({"key": key, "value": val[:100], "key_type": type(k).__name__, "val_type": type(v).__name__})
        identity_headers = [h for h in all_headers if 'x-' in h['key'].lower() and h['key'].lower() != 'x-auth-token']
        try:
            ctx = await utils.req_context_from_scope(request.scope)
            return {
                "user_id": ctx.user_id,
                "project_id": ctx.project_id,
                "roles": ctx.roles,
                "is_admin": 'admin' in (ctx.roles or []),
                "identity_headers": identity_headers,
                "total_headers": len(all_headers),
            }
        except Exception as e:
            return {"error": str(e), "identity_headers": identity_headers, "total_headers": len(all_headers)}

    @app.get("/forecasting")
    async def forecasting_ui():
        from fastapi.responses import HTMLResponse
        from pathlib import Path
        html_path = Path(__file__).parent / "templates" / "forecasting.html"
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    return app


def asgi_app(**kwargs):

    oslo_config_file = os.environ['oslo_config_file']
    service.prepare_service(oslo_config_file)

    config_base_path = os.environ['config_base_path']
    paste_file = kwargs.get('paste_file', 'api_paste.ini')

    return (
        paste.deploy.loadapp(
            'config:%s' % paste_file,
            relative_to=config_base_path,
        )
    )