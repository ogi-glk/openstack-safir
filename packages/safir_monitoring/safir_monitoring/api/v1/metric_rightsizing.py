from __future__ import annotations

import asyncio
import math
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_log import log as logging

from safir_monitoring.schemas import forecasting as forecast_schemas
from safir_monitoring.schemas.metrics import BadRequestMessage, UnauthorizedMessage, ForbiddenMessage, InternalServerErrorMessage
from safir_monitoring.common import policy, utils, thanos
from safir_monitoring.api.v1.metric import _INTERNAL_LABELS, _TENANT_HIDDEN_LABELS


LOG = logging.getLogger(__name__)

router = APIRouter()


def _classify_vm(vm: dict, cpu_idle: float, mem_idle: float,
                 cpu_over: float, mem_over: float,
                 cpu_under: float, mem_under: float,
                 disk_io_daily_mb: float = 2000.0,
                 net_io_daily_mb: float = 300.0) -> str:
    """VM'i kaynak kullanimina gore siniflandirir.

    Idle: CPU VE memory VE disk I/O VE network I/O dusuk (tumu ayni anda)
    Oncelik sirasi: idle > under_provisioned > over_provisioned > right_sized
    """
    avg_cpu = vm.get("avg_cpu", 0) or 0
    avg_memory = vm.get("avg_memory", 0) or 0
    max_cpu = vm.get("max_cpu", 0) or 0
    max_memory = vm.get("max_memory", 0) or 0
    vm_disk_io_mb = vm.get("daily_disk_io_mb", 0) or 0
    vm_net_io_mb = vm.get("daily_net_io_mb", 0) or 0

    # Idle: CPU VE memory VE disk I/O VE network I/O dusuk
    if (avg_cpu < cpu_idle and avg_memory < mem_idle
            and vm_disk_io_mb < disk_io_daily_mb
            and vm_net_io_mb < net_io_daily_mb):
        return "idle"

    # Under-provisioned: ortalama cok yuksek
    if avg_cpu > cpu_under or avg_memory > mem_under:
        return "under_provisioned"

    # Over-provisioned: max bile dusuk
    if max_cpu < cpu_over and max_memory < mem_over:
        return "over_provisioned"

    return "right_sized"


def _compute_recommendation(category: str, max_cpu: float, max_memory: float,
                            allocated_vcpu: int, allocated_memory_gb: float,
                            over_threshold: float = 30) -> dict:
    """Rightsizing onerisi hesaplar.

    Over-provisioned: max kullanimi hedef yuzdede tutacak kaynak onerisi
    Under-provisioned: max kullanimi %70 civarinda tutacak kaynak onerisi
    """
    if category == "over_provisioned":
        # max_cpu %30 esiginde olacak sekilde vCPU onerisi
        target_cpu_pct = over_threshold / 100
        rec_vcpu = max(1, math.ceil(allocated_vcpu * (max_cpu / 100) / target_cpu_pct))
        rec_memory = max(1.0, round(allocated_memory_gb * (max_memory / 100) / target_cpu_pct, 1))
        return {"vcpu": rec_vcpu, "memory_gb": rec_memory}

    elif category == "under_provisioned":
        # max kullanimi %70'e dusecek sekilde kaynak artir
        target_pct = 0.70
        rec_vcpu = max(allocated_vcpu + 1, math.ceil(allocated_vcpu * (max_cpu / 100) / target_pct))
        rec_memory = max(allocated_memory_gb + 1, round(allocated_memory_gb * (max_memory / 100) / target_pct, 1))
        return {"vcpu": rec_vcpu, "memory_gb": rec_memory}

    return {"vcpu": allocated_vcpu, "memory_gb": allocated_memory_gb}


async def _fetch_vm_rightsizing_data(project_id: str = None, period_days: int = 7, is_admin: bool = False) -> list:
    """VM metriklerini MySQL vm_metrics_hourly tablosundan ceker.

    Collector tarafindan saatlik olarak Thanos'tan cekilip MySQL'e yazilan
    veriler burada aggregate edilir. API worker'lari Thanos'a gitmez.
    """
    from safir_monitoring.db.base import DB, inject_db

    await inject_db()
    db = DB.get()
    cutoff = datetime.now() - timedelta(days=period_days)

    # project_id filtresi
    if project_id:
        query = """
            SELECT instance_id, instance_name, project_id, hostname,
                   AVG(avg_cpu) as avg_cpu,
                   MAX(max_cpu) as max_cpu,
                   AVG(avg_memory) as avg_memory,
                   MAX(max_memory) as max_memory,
                   AVG(disk_io_bytes_sec) as avg_disk_io_bytes_sec,
                   AVG(net_io_bytes_sec) as avg_net_io_bytes_sec,
                   MAX(allocated_vcpu) as allocated_vcpu,
                   MAX(allocated_memory_bytes) as allocated_memory_bytes
            FROM vm_metrics_hourly
            WHERE timestamp >= :cutoff AND project_id = :project_id
            GROUP BY instance_id, instance_name, project_id, hostname
        """
        rows = await db.fetch_all(query=query, values={"cutoff": cutoff, "project_id": project_id})
    else:
        query = """
            SELECT instance_id, instance_name, project_id, hostname,
                   AVG(avg_cpu) as avg_cpu,
                   MAX(max_cpu) as max_cpu,
                   AVG(avg_memory) as avg_memory,
                   MAX(max_memory) as max_memory,
                   AVG(disk_io_bytes_sec) as avg_disk_io_bytes_sec,
                   AVG(net_io_bytes_sec) as avg_net_io_bytes_sec,
                   MAX(allocated_vcpu) as allocated_vcpu,
                   MAX(allocated_memory_bytes) as allocated_memory_bytes
            FROM vm_metrics_hourly
            WHERE timestamp >= :cutoff
            GROUP BY instance_id, instance_name, project_id, hostname
        """
        rows = await db.fetch_all(query=query, values={"cutoff": cutoff})

    vm_list = []
    for row in rows:
        r = dict(row._mapping)
        disk_io = r.get("avg_disk_io_bytes_sec")
        net_io = r.get("avg_net_io_bytes_sec")
        alloc_mem = r.get("allocated_memory_bytes")

        vm = {
            "instance_id": r["instance_id"],
            "name": r.get("instance_name") or "unknown",
            "project_id": r.get("project_id") or "",
            "hostname": r.get("hostname", "") if is_admin else "",
            "avg_cpu": round(r["avg_cpu"], 2) if r.get("avg_cpu") is not None else None,
            "max_cpu": round(r["max_cpu"], 2) if r.get("max_cpu") is not None else None,
            "avg_memory": round(r["avg_memory"], 2) if r.get("avg_memory") is not None else None,
            "max_memory": round(r["max_memory"], 2) if r.get("max_memory") is not None else None,
            "avg_disk_io_bytes_sec": round(disk_io, 2) if disk_io is not None else None,
            "avg_net_io_bytes_sec": round(net_io, 2) if net_io is not None else None,
            "daily_disk_io_mb": round(disk_io * 86400 / (1024 * 1024), 2) if disk_io is not None else None,
            "daily_net_io_mb": round(net_io * 86400 / (1024 * 1024), 2) if net_io is not None else None,
            "allocated_vcpu": int(r["allocated_vcpu"]) if r.get("allocated_vcpu") is not None else None,
            "allocated_memory_gb": round(alloc_mem / (1024 ** 3), 2) if alloc_mem is not None else None,
        }
        vm_list.append(vm)

    return vm_list


# ============================================================================
# RIGHTSIZING ENDPOINTS
# ============================================================================

async def _get_rightsizing_context(request, project_id):
    """Auth ve admin kontrolu yapar, (context, is_admin) dondurur."""
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
        policy.authorize(context, 'metric:get_rightsizing', {"project_id": project_id})

    return context, is_admin


@router.get(
    "/metrics/rightsizing/idle-vms",
    description="List idle VMs (low CPU, memory, disk I/O and network I/O)",
    responses={
        200: {"model": forecast_schemas.RightsizingListResponse},
        401: {"model": UnauthorizedMessage},
        403: {"model": ForbiddenMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.RightsizingListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_idle_vms(
    request: Request,
    period_days: int = Query(7, description="Analysis period in days", ge=1, le=90),
    cpu_threshold: float = Query(5.0, description="CPU idle threshold (%)"),
    memory_threshold: float = Query(10.0, description="Memory idle threshold (%)"),
    disk_io_threshold: float = Query(2000.0, description="Daily disk I/O idle threshold (MB)"),
    net_io_threshold: float = Query(300.0, description="Daily network I/O idle threshold (MB)"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.RightsizingListResponse:
    try:
        context, is_admin = await _get_rightsizing_context(request, project_id)

        vms = await _fetch_vm_rightsizing_data(
            project_id=None if is_admin else project_id,
            period_days=period_days,
            is_admin=is_admin,
        )

        idle_vms = []
        for vm in vms:
            category = _classify_vm(
                vm, cpu_idle=cpu_threshold, mem_idle=memory_threshold,
                cpu_over=30, mem_over=30, cpu_under=80, mem_under=80,
                disk_io_daily_mb=disk_io_threshold, net_io_daily_mb=net_io_threshold,
            )
            if category == "idle":
                idle_vms.append(vm)

        return forecast_schemas.RightsizingListResponse(
            vms=[forecast_schemas.RightsizingVMElement(**v) for v in idle_vms],
            total_count=len(idle_vms),
            period_days=period_days,
            message=f"Found {len(idle_vms)} idle VMs",
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_idle_vms: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/metrics/rightsizing/over-provisioned-vms",
    description="List over-provisioned VMs (max usage below threshold)",
    responses={
        200: {"model": forecast_schemas.RightsizingListResponse},
        401: {"model": UnauthorizedMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.RightsizingListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_over_provisioned_vms(
    request: Request,
    period_days: int = Query(7, description="Analysis period in days", ge=1, le=90),
    max_utilization_threshold: float = Query(30.0, description="Max utilization threshold (%)"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.RightsizingListResponse:
    try:
        context, is_admin = await _get_rightsizing_context(request, project_id)

        vms = await _fetch_vm_rightsizing_data(
            project_id=None if is_admin else project_id,
            period_days=period_days,
            is_admin=is_admin,
        )

        over_vms = []
        for vm in vms:
            category = _classify_vm(
                vm, cpu_idle=5, mem_idle=10,
                cpu_over=max_utilization_threshold, mem_over=max_utilization_threshold,
                cpu_under=80, mem_under=80
            )
            if category == "over_provisioned":
                rec = _compute_recommendation(
                    "over_provisioned",
                    max_cpu=vm.get("max_cpu", 0) or 0,
                    max_memory=vm.get("max_memory", 0) or 0,
                    allocated_vcpu=vm.get("allocated_vcpu", 1) or 1,
                    allocated_memory_gb=vm.get("allocated_memory_gb", 1) or 1,
                    over_threshold=max_utilization_threshold,
                )
                vm["recommendation"] = rec
                over_vms.append(vm)

        return forecast_schemas.RightsizingListResponse(
            vms=[forecast_schemas.RightsizingVMElement(**v) for v in over_vms],
            total_count=len(over_vms),
            period_days=period_days,
            message=f"Found {len(over_vms)} over-provisioned VMs",
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_over_provisioned_vms: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/metrics/rightsizing/under-provisioned-vms",
    description="List under-provisioned VMs (avg usage above threshold)",
    responses={
        200: {"model": forecast_schemas.RightsizingListResponse},
        401: {"model": UnauthorizedMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.RightsizingListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_under_provisioned_vms(
    request: Request,
    period_days: int = Query(7, description="Analysis period in days", ge=1, le=90),
    avg_utilization_threshold: float = Query(80.0, description="Avg utilization threshold (%)"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.RightsizingListResponse:
    try:
        context, is_admin = await _get_rightsizing_context(request, project_id)

        vms = await _fetch_vm_rightsizing_data(
            project_id=None if is_admin else project_id,
            period_days=period_days,
            is_admin=is_admin,
        )

        under_vms = []
        for vm in vms:
            category = _classify_vm(
                vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30,
                cpu_under=avg_utilization_threshold, mem_under=avg_utilization_threshold
            )
            if category == "under_provisioned":
                rec = _compute_recommendation(
                    "under_provisioned",
                    max_cpu=vm.get("max_cpu", 0) or 0,
                    max_memory=vm.get("max_memory", 0) or 0,
                    allocated_vcpu=vm.get("allocated_vcpu", 1) or 1,
                    allocated_memory_gb=vm.get("allocated_memory_gb", 1) or 1,
                )
                vm["recommendation"] = rec
                under_vms.append(vm)

        return forecast_schemas.RightsizingListResponse(
            vms=[forecast_schemas.RightsizingVMElement(**v) for v in under_vms],
            total_count=len(under_vms),
            period_days=period_days,
            message=f"Found {len(under_vms)} under-provisioned VMs",
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_under_provisioned_vms: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/metrics/rightsizing/report",
    description="Combined rightsizing report with all categories",
    responses={
        200: {"model": forecast_schemas.RightsizingReportResponse},
        401: {"model": UnauthorizedMessage},
        500: {"model": InternalServerErrorMessage},
    },
    response_model=forecast_schemas.RightsizingReportResponse,
    status_code=status.HTTP_200_OK,
)
async def get_rightsizing_report(
    request: Request,
    period_days: int = Query(7, description="Analysis period in days", ge=1, le=90),
    cpu_idle_threshold: float = Query(5.0, description="CPU idle threshold (%)"),
    memory_idle_threshold: float = Query(10.0, description="Memory idle threshold (%)"),
    disk_io_idle_threshold: float = Query(2000.0, description="Daily disk I/O idle threshold (MB)"),
    net_io_idle_threshold: float = Query(300.0, description="Daily network I/O idle threshold (MB)"),
    max_utilization_threshold: float = Query(30.0, description="Over-provisioned threshold (%)"),
    avg_utilization_threshold: float = Query(80.0, description="Under-provisioned threshold (%)"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> forecast_schemas.RightsizingReportResponse:
    try:
        context, is_admin = await _get_rightsizing_context(request, project_id)

        vms = await _fetch_vm_rightsizing_data(
            project_id=None if is_admin else project_id,
            period_days=period_days,
            is_admin=is_admin,
        )

        idle_vms = []
        over_vms = []
        under_vms = []
        right_sized_count = 0
        saved_vcpu = 0
        saved_memory_gb = 0.0

        for vm in vms:
            category = _classify_vm(
                vm,
                cpu_idle=cpu_idle_threshold, mem_idle=memory_idle_threshold,
                cpu_over=max_utilization_threshold, mem_over=max_utilization_threshold,
                cpu_under=avg_utilization_threshold, mem_under=avg_utilization_threshold,
                disk_io_daily_mb=disk_io_idle_threshold, net_io_daily_mb=net_io_idle_threshold,
            )

            if category == "idle":
                saved_vcpu += vm.get("allocated_vcpu", 0) or 0
                saved_memory_gb += vm.get("allocated_memory_gb", 0) or 0
                idle_vms.append(vm)
            elif category == "over_provisioned":
                alloc_vcpu = vm.get("allocated_vcpu", 1) or 1
                alloc_mem = vm.get("allocated_memory_gb", 1) or 1
                rec = _compute_recommendation(
                    "over_provisioned",
                    max_cpu=vm.get("max_cpu", 0) or 0,
                    max_memory=vm.get("max_memory", 0) or 0,
                    allocated_vcpu=alloc_vcpu,
                    allocated_memory_gb=alloc_mem,
                    over_threshold=max_utilization_threshold,
                )
                vm["recommendation"] = rec
                saved_vcpu += alloc_vcpu - rec["vcpu"]
                saved_memory_gb += alloc_mem - rec["memory_gb"]
                over_vms.append(vm)
            elif category == "under_provisioned":
                rec = _compute_recommendation(
                    "under_provisioned",
                    max_cpu=vm.get("max_cpu", 0) or 0,
                    max_memory=vm.get("max_memory", 0) or 0,
                    allocated_vcpu=vm.get("allocated_vcpu", 1) or 1,
                    allocated_memory_gb=vm.get("allocated_memory_gb", 1) or 1,
                )
                vm["recommendation"] = rec
                under_vms.append(vm)
            else:
                right_sized_count += 1

        return forecast_schemas.RightsizingReportResponse(
            summary=forecast_schemas.RightsizingSummary(
                total_vms=len(vms),
                idle=len(idle_vms),
                over_provisioned=len(over_vms),
                under_provisioned=len(under_vms),
                right_sized=right_sized_count,
            ),
            idle_vms=[forecast_schemas.RightsizingVMElement(**v) for v in idle_vms],
            over_provisioned_vms=[forecast_schemas.RightsizingVMElement(**v) for v in over_vms],
            under_provisioned_vms=[forecast_schemas.RightsizingVMElement(**v) for v in under_vms],
            potential_savings=forecast_schemas.PotentialSavings(
                vcpu=max(0, saved_vcpu),
                memory_gb=round(max(0, saved_memory_gb), 2),
            ),
            period_days=period_days,
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_rightsizing_report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
