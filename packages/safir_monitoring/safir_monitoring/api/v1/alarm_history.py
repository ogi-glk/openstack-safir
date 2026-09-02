from __future__ import annotations

import aiohttp
import ssl
from typing import List, Optional
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_config import cfg
from pydantic import BaseModel
from oslo_log import log as logging

from safir_monitoring.common import policy, utils

LOG = logging.getLogger(__name__)

router = APIRouter()
CONF = cfg.CONF


class AlarmHistoryItem(BaseModel):
    id: str
    timestamp: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[str] = None
    alert_name: Optional[str] = None
    severity: Optional[str] = None
    cluster: Optional[str] = None
    fingerprint: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    labels: Optional[dict] = None
    annotations: Optional[dict] = None


class AlarmHistoryResponse(BaseModel):
    total: int
    from_: int
    size: int
    items: List[AlarmHistoryItem]


def _get_ssl_connector():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return aiohttp.TCPConnector(ssl=ssl_context)


def _validate_scope(scope: str, context):
    if scope not in ("console", "admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope must be 'console' or 'admin'"
        )
    if scope == "admin" and "admin" not in (context.roles or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin scope requires admin role"
        )


def _resolve_project_id(scope: str, context) -> str:
    if scope == "admin":
        return "system"
    if not context.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id not found in token for console scope"
        )
    return context.project_id


@router.get(
    "/{scope}/alarm-history",
    description="List alarm history (console: token project, admin: system) from OpenSearch",
    responses={
        200: {"model": AlarmHistoryResponse},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        500: {"description": "Internal server error"},
    },
    response_model=AlarmHistoryResponse,
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def list_alarm_history(
    scope: str,
    request: Request,
    from_: int = Query(0, alias="from", description="Pagination offset", ge=0),
    size: int = Query(10, description="Number of results to return", ge=1, le=100),
    severity: Optional[str] = Query(None, description="Filter by severity (e.g. critical, warning)"),
    alert_status: Optional[str] = Query(None, description="Filter by status (firing, resolved)"),
    X_Auth_Token: str = Header(default=None)
) -> AlarmHistoryResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        _validate_scope(scope, context)
        project_id = _resolve_project_id(scope, context)
        policy.authorize(context, 'alarm_history:list', {"project_id": project_id})

        opensearch_url = CONF.opensearch.url
        index_name = f"alarm-{project_id}"
        url = f"{opensearch_url}/{index_name}/_search"

        must_clauses = []

        if severity:
            must_clauses.append({"term": {"severity.keyword": severity}})

        if alert_status:
            must_clauses.append({"term": {"status.keyword": alert_status}})

        query = {
            "from": from_,
            "size": size,
            "sort": [{"timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": must_clauses if must_clauses else [{"match_all": {}}]
                }
            }
        }

        auth = aiohttp.BasicAuth(CONF.opensearch.username, CONF.opensearch.password)
        connector = _get_ssl_connector()

        async with aiohttp.ClientSession(connector=connector, auth=auth) as session:
            async with session.post(
                url,
                json=query,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 404:
                    return AlarmHistoryResponse(total=0, from_=from_, size=size, items=[])

                if response.status < 200 or response.status >= 300:
                    error_text = await response.text()
                    raise Exception(f"OpenSearch returned status {response.status}: {error_text}")

                data = await response.json()

        hits = data.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        documents = hits.get("hits", [])

        items = []
        for doc in documents:
            source = doc.get("_source", {})
            items.append(AlarmHistoryItem(
                id=doc["_id"],
                timestamp=source.get("timestamp"),
                status=source.get("status"),
                project_id=source.get("project_id"),
                alert_name=source.get("alert_name"),
                severity=source.get("severity"),
                cluster=source.get("cluster"),
                fingerprint=source.get("fingerprint"),
                starts_at=source.get("starts_at"),
                ends_at=source.get("ends_at"),
                duration_seconds=source.get("duration_seconds"),
                labels=source.get("labels"),
                annotations=source.get("annotations"),
            ))

        return AlarmHistoryResponse(total=total, from_=from_, size=size, items=items)

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in list_alarm_history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
