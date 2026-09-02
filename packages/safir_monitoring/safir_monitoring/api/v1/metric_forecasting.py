from __future__ import annotations

import asyncio
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_log import log as logging

from safir_monitoring.schemas import forecasting as forecast_schemas
from safir_monitoring.schemas.metrics import BadRequestMessage, UnauthorizedMessage, ForbiddenMessage, InternalServerErrorMessage
from safir_monitoring.common import policy, utils, thanos
from safir_monitoring.common.resource_queries import (
    build_host_query, build_host_capacity_query, build_vm_query,
    build_placement_query, build_placement_capacity_query,
    VALID_RESOURCE_TYPES, VALID_METRIC_SOURCES,
)


LOG = logging.getLogger(__name__)

VALID_ALGORITHMS = {"prophet", "arima"}


def _get_forecaster(algorithm: str, daily_data, total_capacity, future_days):
    """Algorithm parametresine gore uygun forecaster dondurur."""
    if algorithm == "arima":
        from safir_monitoring.common.arima_forecaster import ArimaForecaster
        return ArimaForecaster(daily_data, total_capacity, future_days=future_days)
    else:
        from safir_monitoring.common.prophet_forecaster import ProphetForecaster
        return ProphetForecaster(daily_data, total_capacity, future_days=future_days)


def _validate_algorithm(algorithm: str):
    if algorithm not in VALID_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid algorithm: {algorithm}. Valid: {VALID_ALGORITHMS}"
        )

router = APIRouter()


_RESOURCE_COLUMN_MAP = {
    "cpu": "cpu_percent",
    "memory": "memory_percent",
    "disk": "disk_percent",
}

_CAPACITY_COLUMN_MAP = {
    "cpu": None,  # CPU yuzde, kapasite 100
    "memory": "memory_total_bytes",
    "disk": "disk_total_bytes",
}

_PLACEMENT_USAGE_COLUMN_MAP = {
    "cpu": "placement_vcpu_used",
    "memory": "placement_memory_used_mb",
    "disk": "placement_disk_used_gb",
}

_PLACEMENT_CAPACITY_COLUMN_MAP = {
    "cpu": "placement_vcpu_total",
    "memory": "placement_memory_total_mb",
    "disk": "placement_disk_total_gb",
}

_VM_RESOURCE_COLUMN_MAP = {
    "cpu": "avg_cpu",
    "memory": "avg_memory",
    "disk": None,  # VM disk icin ayri hesaplama gerekir
}


async def _fetch_daily_data_from_db(resource_type: str, instance: str = None,
                                     nodename: str = None, days: int = 90) -> list:
    """Host metriklerini MySQL host_metrics_hourly'den ceker ve gunluk aggregate eder.

    Returns:
        [[timestamp_str, value], ...] listesi (Prophet icin uygun format)
    """
    from safir_monitoring.db.base import DB, inject_db
    await inject_db()
    db = DB.get()

    column = _RESOURCE_COLUMN_MAP.get(resource_type)
    if not column:
        return []

    cutoff = datetime.now() - timedelta(days=days)

    if instance:
        query = f"""
            SELECT DATE(timestamp) as day, AVG({column}) as avg_val
            FROM host_metrics_hourly
            WHERE timestamp >= :cutoff AND instance = :instance AND {column} IS NOT NULL
            GROUP BY DATE(timestamp) ORDER BY day
        """
        rows = await db.fetch_all(query=query, values={"cutoff": cutoff, "instance": instance})
    elif nodename:
        query = f"""
            SELECT DATE(timestamp) as day, AVG({column}) as avg_val
            FROM host_metrics_hourly
            WHERE timestamp >= :cutoff AND nodename = :nodename AND {column} IS NOT NULL
            GROUP BY DATE(timestamp) ORDER BY day
        """
        rows = await db.fetch_all(query=query, values={"cutoff": cutoff, "nodename": nodename})
    else:
        # System-wide: tum host'larin ortalamasi
        query = f"""
            SELECT DATE(timestamp) as day, AVG({column}) as avg_val
            FROM host_metrics_hourly
            WHERE timestamp >= :cutoff AND {column} IS NOT NULL
            GROUP BY DATE(timestamp) ORDER BY day
        """
        rows = await db.fetch_all(query=query, values={"cutoff": cutoff})

    daily_data = []
    for row in rows:
        r = dict(row._mapping)
        day_str = r["day"].strftime("%Y-%m-%dT00:00:00Z")
        daily_data.append([day_str, str(round(float(r["avg_val"]), 4))])

    return daily_data


async def _fetch_placement_daily_data_from_db(resource_type: str, nodename: str = None,
                                               days: int = 90) -> tuple:
    """Placement metriklerini MySQL'den ceker.

    Returns:
        (daily_data, total_capacity) tuple'i
    """
    from safir_monitoring.db.base import DB, inject_db
    await inject_db()
    db = DB.get()

    usage_col = _PLACEMENT_USAGE_COLUMN_MAP.get(resource_type)
    cap_col = _PLACEMENT_CAPACITY_COLUMN_MAP.get(resource_type)
    if not usage_col or not cap_col:
        return [], 0

    cutoff = datetime.now() - timedelta(days=days)

    if nodename:
        query = f"""
            SELECT DATE(timestamp) as day,
                   AVG({usage_col}) as avg_usage,
                   AVG({cap_col}) as avg_cap
            FROM host_metrics_hourly
            WHERE timestamp >= :cutoff AND nodename = :nodename
                  AND {usage_col} IS NOT NULL
            GROUP BY DATE(timestamp) ORDER BY day
        """
        rows = await db.fetch_all(query=query, values={"cutoff": cutoff, "nodename": nodename})
    else:
        # System-wide: tum host'larin toplami
        query = f"""
            SELECT DATE(timestamp) as day,
                   SUM({usage_col}) as avg_usage,
                   SUM({cap_col}) as avg_cap
            FROM host_metrics_hourly
            WHERE timestamp >= :cutoff AND {usage_col} IS NOT NULL
            GROUP BY DATE(timestamp) ORDER BY day
        """
        rows = await db.fetch_all(query=query, values={"cutoff": cutoff})

    if not rows:
        return [], 0

    # Son kapasite degeri
    last_row = dict(rows[-1]._mapping)
    total_capacity = float(last_row.get("avg_cap") or 0)
    if resource_type == "memory":
        total_capacity = total_capacity / 1024  # MB -> GB

    daily_data = []
    for row in rows:
        r = dict(row._mapping)
        day_str = r["day"].strftime("%Y-%m-%dT00:00:00Z")
        daily_data.append([day_str, str(round(float(r["avg_usage"]), 4))])

    return daily_data, total_capacity


async def _fetch_vm_daily_data_from_db(resource_type: str, instance_id: str,
                                        days: int = 90) -> list:
    """VM metriklerini MySQL vm_metrics_hourly'den ceker."""
    from safir_monitoring.db.base import DB, inject_db
    await inject_db()
    db = DB.get()

    column = _VM_RESOURCE_COLUMN_MAP.get(resource_type)
    if not column:
        return []

    cutoff = datetime.now() - timedelta(days=days)

    query = f"""
        SELECT DATE(timestamp) as day, AVG({column}) as avg_val
        FROM vm_metrics_hourly
        WHERE timestamp >= :cutoff AND instance_id = :instance_id AND {column} IS NOT NULL
        GROUP BY DATE(timestamp) ORDER BY day
    """
    rows = await db.fetch_all(query=query, values={"cutoff": cutoff, "instance_id": instance_id})

    daily_data = []
    for row in rows:
        r = dict(row._mapping)
        day_str = r["day"].strftime("%Y-%m-%dT00:00:00Z")
        daily_data.append([day_str, str(round(float(r["avg_val"]), 4))])

    return daily_data


async def _get_capacity_from_db(resource_type: str, instance: str = None,
                                 nodename: str = None) -> float:
    """Host kapasite degerini MySQL'den alir."""
    from safir_monitoring.db.base import DB, inject_db
    await inject_db()
    db = DB.get()

    cap_col = _CAPACITY_COLUMN_MAP.get(resource_type)
    if cap_col is None:
        return 100  # CPU yuzde

    if instance:
        query = f"SELECT {cap_col} FROM host_metrics_hourly WHERE instance = :instance AND {cap_col} IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        row = await db.fetch_one(query=query, values={"instance": instance})
    elif nodename:
        query = f"SELECT {cap_col} FROM host_metrics_hourly WHERE nodename = :nodename AND {cap_col} IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        row = await db.fetch_one(query=query, values={"nodename": nodename})
    else:
        return 100

    if row:
        return float(dict(row._mapping)[cap_col])
    return 100


async def _get_capacity_value(resource_type: str, instance: str = None) -> float:
    """Host icin total capacity degerini alir."""
    cap_query = build_host_capacity_query(resource_type, instance)

    if isinstance(cap_query, (int, float)):
        return float(cap_query)

    # PromQL sorgusu — Thanos'tan instant query
    result_str = await thanos.execute_instant_query(cap_query)
    return float(result_str)


def _validate_resource_type(resource_type: str):
    if resource_type not in VALID_RESOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid resource_type: {resource_type}. Valid: {VALID_RESOURCE_TYPES}"
        )


def _validate_metric_source(metric_source: str):
    if metric_source not in VALID_METRIC_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric_source: {metric_source}. Valid: {VALID_METRIC_SOURCES}"
        )


async def _get_placement_capacity(resource_type: str, hostname: str = None) -> float:
    """Placement bazli toplam kapasite degerini alir."""
    cap_query = build_placement_capacity_query(resource_type, hostname)
    result_str = await thanos.execute_instant_query(cap_query)
    return float(result_str)


async def _fetch_placement_daily_data(resource_type: str, hostname: str = None, days: int = 90) -> tuple:
    """Placement usage verisini cekip gunluk yuzdeye cevirir.

    Usage ve capacity ayri cekilir, yuzde Python'da hesaplanir.
    Bu yaklasim Thanos'ta karmasik bolme sorgularinin timeout olmasini onler.

    Returns:
        (daily_data, total_capacity) tuple'i
    """
    usage_query = build_placement_query(resource_type, hostname)

    now = datetime.now()
    end_unix = int(now.timestamp())
    start_unix = int((now - timedelta(days=days)).timestamp())

    # Usage verisini cek
    result = await thanos.execute_range_query_with_time(
        query=usage_query, start=start_unix, end=end_unix, step="24h"
    )

    if not result:
        return [], 0

    # Kapasite degerini ayri cek (instant query — hizli)
    total_capacity = await _get_placement_capacity(resource_type, hostname)
    if total_capacity <= 0:
        return [], 0

    # Tum serileri topla
    all_values = []
    for series in result:
        all_values.extend(series.get("values", []))
    if not all_values:
        return [], 0

    # Gune gore grupla, ortalama al (ham deger — yuzdeye cevirme)
    from collections import defaultdict
    daily_buckets = defaultdict(list)
    for ts, val in all_values:
        day_key = int(ts) // 86400 * 86400
        daily_buckets[day_key].append(float(val))

    from safir_monitoring.api.v1.metric import _ts_to_iso
    daily_data = []
    for day_ts in sorted(daily_buckets.keys()):
        vals = daily_buckets[day_ts]
        avg_usage = sum(vals) / len(vals)
        daily_data.append([_ts_to_iso(day_ts), str(round(avg_usage, 4))])

    # Ham deger + gercek kapasite doner
    # Prophet current_usage=24.5, total_capacity=1212, usage_percentage=2.02% hesaplar
    return daily_data, total_capacity


async def _resolve_hostname_to_instance(hostname: str) -> str:
    """Hostname'i (orn: test-compute1) Thanos instance adresine (orn: 10.0.0.1:9100) cevirir.

    node_uname_info metriginden nodename -> instance eslestirmesi yapar.
    Eger hostname zaten IP:port formatindaysa aynen doner.
    """
    # IP:port formatindaysa direkt don
    if ":" in hostname:
        return hostname

    try:
        result = await thanos.execute_range_query(
            query=f'node_uname_info{{nodename="{hostname}"}}'
        )
        if result:
            instance = result[0].get("metric", {}).get("instance", "")
            if instance:
                LOG.info(f"Resolved hostname '{hostname}' -> instance '{instance}'")
                return instance
    except Exception as e:
        LOG.warning(f"Failed to resolve hostname '{hostname}': {e}")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Host '{hostname}' not found. Use hostname (e.g., 'test-compute1') or instance address (e.g., '10.0.0.1:9100')"
    )


# ============================================================================
# PREDICTION ENDPOINTS
# ============================================================================

@router.get(
    "/metrics/forecasts/prediction",
    description="Get resource prediction for a host or VM",
    responses={
        200: {"model": forecast_schemas.PredictionResponse},
        400: {"model": BadRequestMessage},
        401: {"model": UnauthorizedMessage},
        403: {"model": ForbiddenMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.PredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_prediction(
    request: Request,
    resource_type: str = Query(..., description="Resource type: cpu, memory, disk"),
    dimension: str = Query(..., description="Hostname (e.g., 'test-compute1') or VM instance_id"),
    period_days: int = Query(90, description="Forecast period in days", ge=7, le=365),
    scope: str = Query("host", description="Scope: host or vm"),
    metric_source: str = Query("real", description="Data source: real (node-exporter) or placement (OpenStack Placement)"),
    algorithm: str = Query("prophet", description="Forecasting algorithm: prophet or arima"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin VM predictions)"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.PredictionResponse:
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
            policy.authorize(context, 'metric:get_prediction', {"project_id": project_id})

        _validate_resource_type(resource_type)
        _validate_metric_source(metric_source)
        _validate_algorithm(algorithm)

        # MySQL'den veri cek (Thanos'a gitmez)
        if scope == "vm":
            daily_data = await _fetch_vm_daily_data_from_db(resource_type, instance_id=dimension, days=period_days)
            total_capacity = 100
        elif metric_source == "placement":
            daily_data, total_capacity = await _fetch_placement_daily_data_from_db(resource_type, nodename=dimension, days=period_days)
        else:
            daily_data = await _fetch_daily_data_from_db(resource_type, nodename=dimension, days=period_days)
            total_capacity = await _get_capacity_from_db(resource_type, nodename=dimension)

        LOG.info(f"Prediction from DB: {resource_type}, dim={dimension}, source={metric_source}, days={len(daily_data)}")

        if len(daily_data) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough data points for prediction (minimum 2 days required)"
            )

        forecaster = _get_forecaster(algorithm, daily_data, total_capacity, period_days)
        result = forecaster.get_prediction_result(
            resource_type=resource_type,
            extra_fields={"dimension": dimension, "metric_source": metric_source}
        )

        return forecast_schemas.PredictionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_prediction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/forecasts/prediction/system",
    description="Get system-wide resource prediction (admin only)",
    responses={
        200: {"model": forecast_schemas.PredictionResponse},
        401: {"model": UnauthorizedMessage},
        403: {"model": ForbiddenMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.PredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_prediction_system(
    request: Request,
    resource_type: str = Query(..., description="Resource type: cpu, memory, disk"),
    period_days: int = Query(90, description="Forecast period in days", ge=7, le=365),
    metric_source: str = Query("real", description="Data source: real (node-exporter) or placement (OpenStack Placement)"),
    algorithm: str = Query("prophet", description="Forecasting algorithm: prophet or arima"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.PredictionResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_prediction_system', {})

        _validate_resource_type(resource_type)
        _validate_metric_source(metric_source)
        _validate_algorithm(algorithm)

        if metric_source == "placement":
            daily_data, total_capacity = await _fetch_placement_daily_data_from_db(resource_type, days=period_days)
        else:
            daily_data = await _fetch_daily_data_from_db(resource_type, days=period_days)
            total_capacity = 100

        LOG.info(f"System prediction from DB: {resource_type}, source={metric_source}, days={len(daily_data)}")

        if len(daily_data) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough data points for system prediction"
            )

        forecaster = _get_forecaster(algorithm, daily_data, total_capacity, period_days)
        result = forecaster.get_prediction_result(
            resource_type=resource_type,
            extra_fields={"scope": "system", "metric_source": metric_source}
        )

        return forecast_schemas.PredictionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_prediction_system: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/forecasts/prediction/system/report",
    description="Get system-wide prediction report for all resource types (admin only)",
    responses={
        200: {"model": forecast_schemas.SystemReportResponse},
        401: {"model": UnauthorizedMessage},
        403: {"model": ForbiddenMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.SystemReportResponse,
    status_code=status.HTTP_200_OK,
)
async def get_prediction_system_report(
    request: Request,
    period_days: int = Query(90, description="Forecast period in days", ge=7, le=365),
    metric_source: str = Query("real", description="Data source: real (node-exporter) or placement (OpenStack Placement)"),
    algorithm: str = Query("prophet", description="Forecasting algorithm: prophet or arima"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.SystemReportResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_prediction_system', {})

        _validate_metric_source(metric_source)
        _validate_algorithm(algorithm)

        report = {}
        for rt in ["cpu", "memory", "disk"]:
            try:
                if metric_source == "placement":
                    daily_data, total_capacity = await _fetch_placement_daily_data_from_db(rt, days=period_days)
                else:
                    daily_data = await _fetch_daily_data_from_db(rt, days=period_days)
                    total_capacity = 100

                if len(daily_data) < 2:
                    report[rt] = {
                        "status": "no_data",
                        "current_usage": 0,
                        "total_capacity": total_capacity,
                        "usage_percentage": 0,
                        "daily_growth": 0,
                        "capacity_full_date": "Insufficient data",
                        "days_remaining": "Insufficient data",
                    }
                    continue

                forecaster = _get_forecaster(algorithm, daily_data, total_capacity, period_days)
                pred = forecaster.get_prediction_result(rt)
                report[rt] = {
                    "status": pred["status"],
                    "current_usage": pred["current_usage"],
                    "total_capacity": pred["total_capacity"],
                    "usage_percentage": pred["usage_percentage"],
                    "daily_growth": pred["daily_growth"],
                    "capacity_full_date": pred["capacity_full_date"],
                    "days_remaining": pred["days_remaining"],
                }
            except Exception as e:
                LOG.warning(f"Failed to generate prediction for {rt}: {e}")
                report[rt] = {
                    "status": "error",
                    "current_usage": 0,
                    "total_capacity": 100,
                    "usage_percentage": 0,
                    "daily_growth": 0,
                    "capacity_full_date": str(e),
                    "days_remaining": str(e),
                }

        return forecast_schemas.SystemReportResponse(
            report={k: forecast_schemas.SystemReportResource(**v) for k, v in report.items()},
            period_days=period_days,
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_prediction_system_report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# TREND GRAPH ENDPOINTS
# ============================================================================

@router.get(
    "/metrics/forecasts/trend-graph",
    description="Get trend graph data for a host or VM",
    responses={
        200: {"model": forecast_schemas.TrendGraphResponse},
        400: {"model": BadRequestMessage},
        401: {"model": UnauthorizedMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.TrendGraphResponse,
    status_code=status.HTTP_200_OK,
)
async def get_trend_graph(
    request: Request,
    resource_type: str = Query(..., description="Resource type: cpu, memory, disk"),
    dimension: str = Query(..., description="Hostname (e.g., 'test-compute1') or VM instance_id"),
    period_days: int = Query(90, description="Historical period in days", ge=7, le=365),
    scope: str = Query("host", description="Scope: host or vm"),
    metric_source: str = Query("real", description="Data source: real or placement"),
    algorithm: str = Query("prophet", description="Forecasting algorithm: prophet or arima"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.TrendGraphResponse:
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
            policy.authorize(context, 'metric:get_trend_graph', {"project_id": project_id})

        _validate_resource_type(resource_type)
        _validate_metric_source(metric_source)
        _validate_algorithm(algorithm)

        if scope == "vm":
            daily_data = await _fetch_vm_daily_data_from_db(resource_type, instance_id=dimension, days=period_days)
            total_capacity = 100
        elif metric_source == "placement":
            daily_data, total_capacity = await _fetch_placement_daily_data_from_db(resource_type, nodename=dimension, days=period_days)
        else:
            daily_data = await _fetch_daily_data_from_db(resource_type, nodename=dimension, days=period_days)
            total_capacity = await _get_capacity_from_db(resource_type, nodename=dimension)

        if len(daily_data) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough data points for trend graph"
            )

        forecaster = _get_forecaster(algorithm, daily_data, total_capacity, period_days)
        result = forecaster.get_trend_graph_result(
            resource_type=resource_type,
            dimension=dimension,
        )

        return forecast_schemas.TrendGraphResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_trend_graph: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/forecasts/trend-graph/system",
    description="Get system-wide trend graph (admin only)",
    responses={
        200: {"model": forecast_schemas.TrendGraphResponse},
        401: {"model": UnauthorizedMessage},
        403: {"model": ForbiddenMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.TrendGraphResponse,
    status_code=status.HTTP_200_OK,
)
async def get_trend_graph_system(
    request: Request,
    resource_type: str = Query(..., description="Resource type: cpu, memory, disk"),
    period_days: int = Query(90, description="Historical period in days", ge=7, le=365),
    metric_source: str = Query("real", description="Data source: real or placement"),
    algorithm: str = Query("prophet", description="Forecasting algorithm: prophet or arima"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.TrendGraphResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_trend_graph_system', {})

        _validate_resource_type(resource_type)
        _validate_metric_source(metric_source)
        _validate_algorithm(algorithm)

        if metric_source == "placement":
            daily_data, total_cap = await _fetch_placement_daily_data_from_db(resource_type, days=period_days)
        else:
            daily_data = await _fetch_daily_data_from_db(resource_type, days=period_days)
            total_cap = 100

        if len(daily_data) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough data points for system trend graph"
            )

        forecaster = _get_forecaster(algorithm, daily_data, total_cap, period_days)
        result = forecaster.get_trend_graph_result(
            resource_type=resource_type,
        )
        result["scope"] = "system"
        result["metric_source"] = metric_source

        return forecast_schemas.TrendGraphResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_trend_graph_system: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# MAX VALUE ENDPOINT
# ============================================================================

@router.get(
    "/metrics/forecasts/max-value",
    description="Get predicted maximum value for a host or VM",
    responses={
        200: {"model": forecast_schemas.MaxValueResponse},
        400: {"model": BadRequestMessage},
        401: {"model": UnauthorizedMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.MaxValueResponse,
    status_code=status.HTTP_200_OK,
)
async def get_max_value(
    request: Request,
    resource_type: str = Query(..., description="Resource type: cpu, memory, disk"),
    dimension: str = Query(..., description="Hostname (e.g., 'test-compute1') or VM instance_id"),
    period_days: int = Query(30, description="Forecast period in days", ge=7, le=365),
    scope: str = Query("host", description="Scope: host or vm"),
    metric_source: str = Query("real", description="Data source: real or placement"),
    algorithm: str = Query("prophet", description="Forecasting algorithm: prophet or arima"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.MaxValueResponse:
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
            policy.authorize(context, 'metric:get_max_value', {"project_id": project_id})

        _validate_resource_type(resource_type)
        _validate_metric_source(metric_source)
        _validate_algorithm(algorithm)

        if scope == "vm":
            daily_data = await _fetch_vm_daily_data_from_db(resource_type, instance_id=dimension, days=period_days)
            total_capacity = 100
        elif metric_source == "placement":
            daily_data, total_capacity = await _fetch_placement_daily_data_from_db(resource_type, nodename=dimension, days=period_days)
        else:
            daily_data = await _fetch_daily_data_from_db(resource_type, nodename=dimension, days=period_days)
            total_capacity = await _get_capacity_from_db(resource_type, nodename=dimension)

        if len(daily_data) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not enough data points for max value prediction"
            )

        current_max = max(float(d[1]) for d in daily_data)

        forecaster = _get_forecaster(algorithm, daily_data, total_capacity, period_days)

        # Future predictions'dan upper bound max'i al
        predicted_max = float(forecaster.future['yhat_upper'].max()) if len(forecaster.future) > 0 else current_max

        return forecast_schemas.MaxValueResponse(
            resource_type=resource_type,
            dimension=dimension,
            current_max=round(current_max, 2),
            predicted_max=round(predicted_max, 2),
            period_days=period_days,
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_max_value: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
