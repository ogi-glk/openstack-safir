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

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_log import log as logging
import json
from pathlib import Path
from safir_monitoring.schemas import metrics as metric_schemas
from safir_monitoring.common import policy, utils, thanos


LOG = logging.getLogger(__name__)

router = APIRouter()

METRIC_LIST_PATH = Path(__file__).parent.parent.parent / "common" / "metric.json"


def parse_time_to_unix(time_str: Optional[str]) -> Optional[int]:
    if not time_str:
        return None

    try:
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except Exception as e:
        LOG.warning(f"Failed to parse time string '{time_str}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time format. Use ISO format (e.g., '2026-02-16T10:00:00Z')"
        )


def _build_query(metric: str, project_id: Optional[str]) -> str:
    """
    Metrik adına ve project_id'ye göre PromQL query oluşturur.

    - libvirt_ ile başlayan metrikler: instance_id ve instance_name label'ları
      zaten Thanos'ta mevcut, ek join gerekmez.
    - host_ veya node_ ile başlayan metrikler: nodename label'ı için
      node_uname_info metriği ile join yapılır.
    - project_id verilmişse uygun label filtresi eklenir.
    """
    is_libvirt = metric.startswith("libvirt_")
    is_host = metric.startswith("host_") or metric.startswith("node_")
    is_openstack = "openstack_" in metric

    # project_id filtresi
    base_query = metric
    if project_id:
        label = "tenant_id" if is_openstack else "project_id"
        if "{" in metric:
            base_query = metric.replace("{", f'{{{label}="{project_id}",')
        else:
            base_query = f'{metric}{{{label}="{project_id}"}}'

    # host/node metriklerine nodename join'i ekle
    if is_host:
        base_query = (
            f'{base_query} * on(instance) group_left(nodename) node_uname_info'
        )
        LOG.info(f"Host metric detected, nodename join applied: {base_query}")

    elif is_libvirt:
        LOG.info(f"Libvirt metric detected, instance_id/instance_name already in labels")

    return base_query


@router.get(
    "/metrics",
    description="Query time series metrics from Thanos (policy: admin or owner)",
    responses={
        200: {"model": metric_schemas.MetricSuccessResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.MetricSuccessResponse,
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def get_metrics(
    request: Request,
    metric: str = Query(..., description="Metric name or PromQL query"),
    start_time: Optional[str] = Query(
        None,
        description="Start time in ISO format (e.g., '2026-02-16T10:00:00Z'). Default: 1 hour ago"
    ),
    end_time: Optional[str] = Query(
        None,
        description="End time in ISO format (e.g., '2026-02-16T11:00:00Z'). Default: now"
    ),
    step: Optional[str] = Query(
        "5m",
        description="Query resolution step (e.g., '5m', '1h'). Default: 5m"
    ),
    project_id: Optional[str] = Query(
        None,
        description="Project ID (required for non-admin users)"
    ),
    X_Auth_Token: str = Header(default=None)
) -> metric_schemas.MetricSuccessResponse:
    """
    Thanos'tan zaman serisi metrik verisi çeker.

    - Varsayılan zaman aralığı: Son 1 saat
    - Varsayılan step: 5 dakika
    - PromQL query desteği
    - libvirt_ metrikleri: instance_id ve instance_name label'ları ile döner
    - host_ / node_ metrikleri: nodename label'ı ile döner
    """
    try:
        context = await utils.req_context_from_scope(request.scope)

        # Admin kontrolü
        is_admin = False
        try:
            policy.authorize(context, 'metric:get_admin', {})
            is_admin = True
        except Exception:
            pass

        # Non-admin için project_id zorunlu ve ownership kontrolü
        if not is_admin:
            if not project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="project_id is required for non-admin users"
                )
            policy.authorize(context, 'metric:get', {"project_id": project_id})

        LOG.info(
            f"GetMetrics request received: metric={metric}, "
            f"start_time={start_time}, end_time={end_time}, step={step}, "
            f"project_id={project_id}, is_admin={is_admin}"
        )

        now = datetime.now()

        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

        # Query oluştur
        final_query = _build_query(metric, project_id)
        LOG.info(f"Final query: {final_query}")

        # Query'yi çalıştır
        metric_data = await thanos.execute_range_query_with_time(
            query=final_query,
            start=start_unix,
            end=end_unix,
            step=step
        )

        LOG.info(
            f"Successfully fetched metrics: metric={metric}, "
            f"result_count={len(metric_data)}"
        )

        return metric_schemas.MetricSuccessResponse(
            data=metric_schemas.MetricData(
                metric=metric,
                start_time=start_unix,
                end_time=end_unix,
                step=step,
                results=metric_data
            ),
            message="Metrics fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# INTERNAL LABELS (Thanos response'tan cikarilacak)
# ============================================================================

_INTERNAL_LABELS = {"__name__", "prometheus", "prometheus_replica"}

# Tenant kullanicilarin goremeyecegi label'lar
_TENANT_HIDDEN_LABELS = {"hostname"}


def _ts_to_iso(ts) -> str:
    """Unix timestamp'i ISO 8601 formatina donusturur."""
    from datetime import timezone
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _filter_dimensions(labels: dict, is_admin: bool) -> dict:
    """Label'lardan dimensions olusturur, tenant icin hassas label'lari gizler."""
    excluded = _INTERNAL_LABELS if is_admin else _INTERNAL_LABELS | _TENANT_HIDDEN_LABELS
    return {k: v for k, v in labels.items() if k not in excluded}


def _format_measurements(metric_name: str, thanos_result: list, is_admin: bool = False) -> list:
    """Thanos query_range sonucunu measurements formatina donusturur."""
    series_list = []
    for series in thanos_result:
        labels = series.get("metric", {})
        dimensions = _filter_dimensions(labels, is_admin)
        raw_values = series.get("values", [])
        measurements = [[_ts_to_iso(ts), val] for ts, val in raw_values]
        series_list.append({
            "name": metric_name,
            "dimensions": dimensions,
            "measurements": measurements,
        })
    return series_list


@router.get(
    "/metrics/measurements",
    description="Query time series measurements from Thanos (policy: admin or owner)",
    responses={
        200: {"model": metric_schemas.MeasurementsResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.MeasurementsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_measurements(
    request: Request,
    name: str = Query(..., description="Metric name (e.g., 'cpu_usage_active')"),
    dimensions: Optional[str] = Query(
        None,
        description="Label filter, format: 'key:value,key2:value2'"
    ),
    start_time: Optional[str] = Query(
        None,
        description="Start time in ISO format. Default: 1 hour ago"
    ),
    end_time: Optional[str] = Query(
        None,
        description="End time in ISO format. Default: now"
    ),
    step: Optional[str] = Query("5m", description="Query resolution step. Default: 5m"),
    merge_metrics: Optional[bool] = Query(False, description="Combine multiple series into one"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.MeasurementsResponse:
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
            policy.authorize(context, 'metric:get_measurements', {"project_id": project_id})

        now = datetime.now()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

        # PromQL query olustur
        query = _build_query(name, project_id if not is_admin else None)

        # Dimension filtresi ekle
        if dimensions:
            dim_filter = ",".join(
                f'{k}="{v}"' for k, v in
                (d.split(":", 1) for d in dimensions.split(",") if ":" in d)
            )
            if "{" in query:
                query = query.replace("{", "{" + dim_filter + ",", 1)
            else:
                query = f"{query}{{{dim_filter}}}"

        if merge_metrics:
            query = f"sum({query})"

        LOG.info(f"Measurements query: {query}")

        thanos_result = await thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step=step
        )

        series = _format_measurements(name, thanos_result, is_admin=is_admin)

        return metric_schemas.MeasurementsResponse(
            data=[metric_schemas.MeasurementSeries(**s) for s in series],
            message="Measurements fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_measurements: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def _compute_statistics(values: list, statistics: list, period: int = None) -> list:
    """Thanos values listesinden istatistikleri hesaplar.

    Args:
        values: [[timestamp, value_str], ...] formatinda zaman serisi
        statistics: Hesaplanacak istatistikler listesi (avg, min, max, count, sum)
        period: Aggregation periyodu (saniye). None ise tum veri tek bucket.

    Returns:
        [[timestamp, stat1, stat2, ...], ...] formatinda sonuc
    """
    if not values:
        return []

    # Float'a cevir
    parsed = [(v[0], float(v[1])) for v in values]

    # Period'a gore bucket'la
    if period and period > 0:
        start_ts = parsed[0][0]
        buckets = {}
        for ts, val in parsed:
            bucket_key = start_ts + ((ts - start_ts) // period) * period
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(val)
        bucket_list = sorted(buckets.items())
    else:
        bucket_list = [(parsed[0][0], [v for _, v in parsed])]

    # Her bucket icin istatistikleri hesapla
    result = []
    stat_funcs = {
        "avg": lambda vals: sum(vals) / len(vals),
        "min": lambda vals: min(vals),
        "max": lambda vals: max(vals),
        "count": lambda vals: len(vals),
        "sum": lambda vals: sum(vals),
    }

    for ts, vals in bucket_list:
        row = [ts]
        for stat in statistics:
            func = stat_funcs.get(stat)
            if func:
                row.append(func(vals))
        result.append(row)

    return result


VALID_STATISTICS = {"avg", "min", "max", "count", "sum"}


@router.get(
    "/metrics/statistics",
    description="Get aggregated statistics for a metric (policy: admin or owner)",
    responses={
        200: {"model": metric_schemas.StatisticsResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.StatisticsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_statistics(
    request: Request,
    name: str = Query(..., description="Metric name"),
    statistics: str = Query(..., description="Comma-separated: avg,min,max,count,sum"),
    dimensions: Optional[str] = Query(None, description="Label filter: 'key:value,key2:value2'"),
    start_time: Optional[str] = Query(None, description="Start time ISO format. Default: 1 hour ago"),
    end_time: Optional[str] = Query(None, description="End time ISO format. Default: now"),
    period: Optional[int] = Query(None, description="Aggregation period in seconds"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.StatisticsResponse:
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
            policy.authorize(context, 'metric:get_statistics', {"project_id": project_id})

        # statistics parametresini dogrula
        stat_list = [s.strip() for s in statistics.split(",")]
        invalid = set(stat_list) - VALID_STATISTICS
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistics: {invalid}. Valid: {VALID_STATISTICS}"
            )

        now = datetime.now()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

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

        # Thanos'tan ham veriyi cek
        resolution_step = f"{period}s" if period else "60s"

        LOG.info(f"Statistics query: {query}, stats={stat_list}, period={period}")

        thanos_result = await thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step=resolution_step
        )

        # Her seri icin istatistikleri hesapla
        columns = ["timestamp"] + stat_list
        series_list = []
        for series in thanos_result:
            labels = series.get("metric", {})
            dims = _filter_dimensions(labels, is_admin)
            values = series.get("values", [])
            stats = _compute_statistics(values, stat_list, period=period)
            # Timestamp'leri ISO formatina cevir
            for row in stats:
                row[0] = _ts_to_iso(row[0])
            series_list.append(
                metric_schemas.StatisticsSeries(
                    name=name,
                    dimensions=dims,
                    columns=columns,
                    statistics=stats,
                )
            )

        return metric_schemas.StatisticsResponse(
            data=series_list,
            message="Statistics fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/list",
    description="List available metrics by type (user: any authenticated, system: admin only)",
    responses={
        200: {"description": "List of metric names"},
        400: {"description": "Invalid type parameter"},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def list_metrics(
    request: Request,
    type: str = Query(..., description="Metric type: 'user' or 'system'"),
    X_Auth_Token: str = Header(default=None)
):
    try:
        context = await utils.req_context_from_scope(request.scope)

        if type == "system":
            policy.authorize(context, 'metric:get_admin', {})
        elif type != "user":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid type. Must be 'user' or 'system'",
            )

        with open(METRIC_LIST_PATH, "r") as f:
            metric_list = json.load(f)

        return {"type": type, "metrics": metric_list[type]}

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in list_metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )