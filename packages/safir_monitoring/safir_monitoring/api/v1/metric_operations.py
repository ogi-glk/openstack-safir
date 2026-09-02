from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_log import log as logging

from safir_monitoring.schemas import metrics as metric_schemas
from safir_monitoring.common import policy, utils, thanos
from safir_monitoring.api.v1.metric import (
    _INTERNAL_LABELS, _filter_dimensions, _build_query, parse_time_to_unix,
)


LOG = logging.getLogger(__name__)

router = APIRouter()

_STAT_FUNCS = {
    "avg": lambda vals: sum(vals) / len(vals) if vals else 0,
    "max": lambda vals: max(vals) if vals else 0,
    "min": lambda vals: min(vals) if vals else 0,
}


def _format_top_n_host(thanos_result: list, statistic: str, nodename_map: dict = None) -> list:
    """Thanos topk sonucundan host bazli top-n listesi olusturur.

    Args:
        nodename_map: instance -> nodename eslestirmesi (node_uname_info'dan)
    """
    func = _STAT_FUNCS.get(statistic, _STAT_FUNCS["avg"])
    if nodename_map is None:
        nodename_map = {}
    hosts = []
    for series in thanos_result:
        labels = series.get("metric", {})
        instance = labels.get("instance", "unknown")
        hostname = nodename_map.get(instance, labels.get("nodename", instance))
        values = [float(v[1]) for v in series.get("values", [])]
        value = func(values)
        dims = {k: v for k, v in labels.items()
                if k not in _INTERNAL_LABELS | {"hostname", "nodename"}}
        hosts.append({
            "hostname": hostname,
            "value": round(value, 2),
            "dimensions": dims,
        })
    hosts.sort(key=lambda x: x["value"], reverse=True)
    return hosts


def _format_top_n_vm(thanos_result: list, statistic: str, is_admin: bool) -> list:
    """Thanos topk sonucundan VM bazli top-n listesi olusturur."""
    func = _STAT_FUNCS.get(statistic, _STAT_FUNCS["avg"])
    _vm_extracted = _INTERNAL_LABELS | {"instance_name", "instance_id", "project_id", "hostname", "domain"}
    vms = []
    for series in thanos_result:
        labels = series.get("metric", {})
        values = [float(v[1]) for v in series.get("values", [])]
        value = func(values)
        dims = {k: v for k, v in labels.items() if k not in _vm_extracted}
        if not is_admin:
            dims.pop("hostname", None)
        vm = {
            "vm_name": labels.get("instance_name", labels.get("domain", "unknown")),
            "instance_id": labels.get("instance_id", ""),
            "project_id": labels.get("project_id", ""),
            "hostname": labels.get("hostname", "") if is_admin else "",
            "value": round(value, 2),
            "dimensions": dims,
        }
        vms.append(vm)
    vms.sort(key=lambda x: x["value"], reverse=True)
    return vms


@router.get(
    "/metrics/statistics/top-n-host",
    description="Get top N hosts by metric value (admin only)",
    responses={
        200: {"model": metric_schemas.TopNHostResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.TopNHostResponse,
    status_code=status.HTTP_200_OK,
)
async def get_top_n_host(
    request: Request,
    name: str = Query(..., description="Metric name (e.g., 'node_cpu_seconds_total')"),
    n: int = Query(10, description="Number of results", ge=1, le=100),
    statistic: str = Query("avg", description="Ranking statistic: avg, max, min"),
    start_time: Optional[str] = Query(None, description="Start time ISO format. Default: 1 hour ago"),
    end_time: Optional[str] = Query(None, description="End time ISO format. Default: now"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.TopNHostResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_top_n_host', {})

        if statistic not in _STAT_FUNCS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistic: {statistic}. Valid: avg, max, min"
            )

        now = datetime.now()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

        # Once instance bazinda aggregate et, sonra topk uygula
        query = f"topk({n}, avg by(instance) ({name}))"

        LOG.info(f"Top-N Host query: {query}")

        import asyncio
        thanos_task = thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step="60s"
        )
        # nodename resolve icin node_uname_info instant query (series'ten daha hizli)
        nodename_task = thanos.execute_range_query(query="node_uname_info")
        thanos_result, uname_result = await asyncio.gather(
            thanos_task, nodename_task, return_exceptions=True
        )

        # Thanos sorgusu basarisiz olursa hata firlat
        if isinstance(thanos_result, Exception):
            raise thanos_result

        # nodename resolve basarisiz olursa bos map ile devam et
        nodename_map = {}
        if isinstance(uname_result, list):
            for s in uname_result:
                labels = s.get("metric", s)
                inst = labels.get("instance", "")
                nodename = labels.get("nodename", "")
                if inst and nodename:
                    nodename_map[inst] = nodename
        else:
            LOG.warning(f"Failed to resolve nodenames: {uname_result}")

        elements = _format_top_n_host(thanos_result, statistic, nodename_map)[:n]

        return metric_schemas.TopNHostResponse(
            name=name,
            statistic=statistic,
            elements=[metric_schemas.TopNHostElement(**e) for e in elements],
            message="Top N hosts fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_top_n_host: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/statistics/top-n-vm",
    description="Get top N VMs by metric value (admin sees all, tenant sees own)",
    responses={
        200: {"model": metric_schemas.TopNVMResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.TopNVMResponse,
    status_code=status.HTTP_200_OK,
)
async def get_top_n_vm(
    request: Request,
    name: str = Query(..., description="Metric name (e.g., 'libvirt_domain_cpu_utilization_perc')"),
    n: int = Query(10, description="Number of results", ge=1, le=100),
    statistic: str = Query("avg", description="Ranking statistic: avg, max, min"),
    start_time: Optional[str] = Query(None, description="Start time ISO format. Default: 1 hour ago"),
    end_time: Optional[str] = Query(None, description="End time ISO format. Default: now"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.TopNVMResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)

        is_admin = False
        try:
            policy.authorize(context, 'metric:get_admin', {})
            is_admin = True
        except Exception:
            pass

        if not is_admin:
            if not project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="project_id is required for non-admin users"
                )
            policy.authorize(context, 'metric:get_top_n_vm', {"project_id": project_id})

        if statistic not in _STAT_FUNCS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistic: {statistic}. Valid: avg, max, min"
            )

        now = datetime.now()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

        base_query = _build_query(name, project_id if not is_admin else None)
        query = f"topk({n}, {base_query})"

        LOG.info(f"Top-N VM query: {query}")

        thanos_result = await thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step="60s"
        )

        elements = _format_top_n_vm(thanos_result, statistic, is_admin)[:n]

        return metric_schemas.TopNVMResponse(
            name=name,
            statistic=statistic,
            elements=[metric_schemas.TopNVMElement(**e) for e in elements],
            message="Top N VMs fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_top_n_vm: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# WOW CHANGE
# ============================================================================

def _series_key(labels: dict) -> str:
    """Seri eslestirme icin label'lardan tekil anahtar uretir."""
    filtered = {k: v for k, v in sorted(labels.items())
                if k not in {"__name__", "prometheus", "prometheus_replica"}}
    return str(filtered)


def _compute_wow_change(current_result: list, previous_result: list, statistic: str, is_admin: bool, nodename_map: dict = None) -> list:
    """Iki haftanin Thanos sonuclarindan WoW degisim hesaplar."""
    if not current_result:
        return []
    if nodename_map is None:
        nodename_map = {}

    func = _STAT_FUNCS.get(statistic, _STAT_FUNCS["avg"])

    prev_map = {}
    for series in previous_result:
        key = _series_key(series.get("metric", {}))
        values = [float(v[1]) for v in series.get("values", [])]
        prev_map[key] = func(values) if values else 0

    elements = []
    for series in current_result:
        labels = series.get("metric", {})
        key = _series_key(labels)
        values = [float(v[1]) for v in series.get("values", [])]
        current_val = func(values) if values else 0
        previous_val = prev_map.get(key, 0)

        change = round(current_val - previous_val, 2)
        change_pct = round((change / previous_val) * 100, 2) if previous_val != 0 else None

        dims = _filter_dimensions(labels, is_admin)
        # instance'i nodename ile degistir
        instance = labels.get("instance", "")
        if instance and instance in nodename_map:
            dims["nodename"] = nodename_map[instance]

        elements.append({
            "dimensions": dims,
            "current_week_value": round(current_val, 2),
            "previous_week_value": round(previous_val, 2),
            "change": change,
            "change_percent": change_pct,
        })

    return elements


@router.get(
    "/metrics/forecasts/wow-change",
    description="Get week-over-week change for a metric",
    responses={
        200: {"model": metric_schemas.WoWChangeResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.WoWChangeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_wow_change(
    request: Request,
    name: str = Query(..., description="Metric name"),
    dimensions: Optional[str] = Query(None, description="Label filter: 'key:value,key2:value2'"),
    statistic: str = Query("avg", description="Comparison statistic: avg, max, min"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.WoWChangeResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)

        is_admin = False
        try:
            policy.authorize(context, 'metric:get_admin', {})
            is_admin = True
        except Exception:
            pass

        if not is_admin:
            if not project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="project_id is required for non-admin users"
                )
            policy.authorize(context, 'metric:get_wow_change', {"project_id": project_id})

        if statistic not in _STAT_FUNCS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistic: {statistic}. Valid: avg, max, min"
            )

        now = datetime.now()
        current_end = int(now.timestamp())
        current_start = int((now - timedelta(days=7)).timestamp())
        previous_end = current_start
        previous_start = int((now - timedelta(days=14)).timestamp())

        query = _build_query(name, project_id if not is_admin else None)

        if dimensions:
            dim_filter = ",".join(
                f'{k}="{v}"' for k, v in
                (d.split(":", 1) for d in dimensions.split(",") if ":" in d)
            )
            if "{" in query:
                query = query.replace("{", "{" + dim_filter + ",", 1)
            else:
                query = f"{query}{{{dim_filter}}}"

        # Instance bazinda aggregate et (cpu/mode gibi alt serileri birlestir)
        query = f"avg by(instance) ({query})"

        LOG.info(f"WoW query: {query}")

        import asyncio
        current_task = thanos.execute_range_query_with_time(
            query=query, start=current_start, end=current_end, step="6h"
        )
        previous_task = thanos.execute_range_query_with_time(
            query=query, start=previous_start, end=previous_end, step="6h"
        )
        nodename_task = thanos.execute_range_query(query="node_uname_info")
        current_result, previous_result, uname_result = await asyncio.gather(
            current_task, previous_task, nodename_task, return_exceptions=True
        )

        if isinstance(current_result, Exception):
            raise current_result
        if isinstance(previous_result, Exception):
            previous_result = []

        # nodename map
        nodename_map = {}
        if isinstance(uname_result, list):
            for s in uname_result:
                labels = s.get("metric", s)
                inst = labels.get("instance", "")
                nodename = labels.get("nodename", "")
                if inst and nodename:
                    nodename_map[inst] = nodename

        elements = _compute_wow_change(current_result, previous_result, statistic, is_admin, nodename_map)

        return metric_schemas.WoWChangeResponse(
            name=name,
            statistic=statistic,
            elements=[metric_schemas.WoWChangeElement(**e) for e in elements],
            message="Week-over-week change calculated successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_wow_change: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
