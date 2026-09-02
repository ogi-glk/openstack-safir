from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_log import log as logging

from safir_monitoring.schemas import metrics as metric_schemas
from safir_monitoring.common import policy, utils, thanos


LOG = logging.getLogger(__name__)

router = APIRouter()

_INTERNAL_LABELS = {"__name__", "prometheus", "prometheus_replica"}


def _format_hosts(series: list) -> list:
    """Thanos series sonucundan host listesi olusturur."""
    hosts = []
    for s in series:
        nodename = s.get("nodename", s.get("instance", "unknown"))
        dimensions = {k: v for k, v in s.items() if k not in _INTERNAL_LABELS and k != "nodename"}
        hosts.append({"name": nodename, "dimensions": dimensions})
    return hosts


def _format_vms(series: list) -> list:
    """Thanos series sonucundan VM listesi olusturur."""
    seen = set()
    vms = []
    _vm_extracted_fields = _INTERNAL_LABELS | {"instance_name", "instance_id", "project_id", "domain", "hostname"}
    for s in series:
        instance_id = s.get("instance_id", "")
        if instance_id in seen:
            continue
        seen.add(instance_id)
        name = s.get("instance_name", s.get("domain", "unknown"))
        project_id = s.get("project_id", "")
        hostname = s.get("hostname", "")
        dimensions = {k: v for k, v in s.items() if k not in _vm_extracted_fields}
        vms.append({
            "name": name,
            "instance_id": instance_id,
            "project_id": project_id,
            "hostname": hostname,
            "dimensions": dimensions,
        })
    return vms


@router.get(
    "/metrics/names",
    description="List available metric names from Thanos",
    responses={
        200: {"model": metric_schemas.MetricNamesResponse},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.MetricNamesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_metric_names(
    request: Request,
    type: Optional[str] = Query(None, description="Filter: 'user' or 'system'"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.MetricNamesResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_names', {"project_id": context.project_id})

        # Tum metrik isimlerini cek, izin verilen prefix'lere gore filtrele
        all_names = await thanos.get_label_values("__name__")

        allowed_prefixes = (
            "libvirt_",       # libvirt-exporter
            "node_",          # node-exporter
            "lxc_",           # lxc-exporter
            "openstack_",     # openstack-exporter
        )
        excluded_prefixes = (
            "node_ethtool_",
        )
        names = [n for n in all_names
                 if n.startswith(allowed_prefixes) and not n.startswith(excluded_prefixes)]

        # Tip filtrelemesi
        if type == "user":
            names = [n for n in names if n.startswith("libvirt_")]
        elif type == "system":
            is_admin = False
            try:
                policy.authorize(context, 'metric:get_admin', {})
                is_admin = True
            except Exception:
                pass
            if not is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="System metrics require admin role"
                )
            names = [n for n in names if not n.startswith("libvirt_")]

        return metric_schemas.MetricNamesResponse(
            metric_names=sorted(names),
            type=type,
            message="Metric names fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_metric_names: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/dimensions/names",
    description="List dimension (label) names for a metric",
    responses={
        200: {"model": metric_schemas.DimensionNamesResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.DimensionNamesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_dimension_names(
    request: Request,
    name: str = Query(..., description="Metric name (required)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.DimensionNamesResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_dimensions', {"project_id": context.project_id})

        labels = await thanos.get_label_names(metric_name=name)

        # Internal label'lari filtrele
        labels = [l for l in labels if l not in _INTERNAL_LABELS]

        return metric_schemas.DimensionNamesResponse(
            dimension_names=sorted(labels),
            message="Dimension names fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_dimension_names: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/dimensions/values",
    description="List values for a specific dimension (label)",
    responses={
        200: {"model": metric_schemas.DimensionValuesResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.DimensionValuesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_dimension_values(
    request: Request,
    dimension_name: str = Query(..., description="Dimension/label key (required)"),
    name: Optional[str] = Query(None, description="Metric name for filtering"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.DimensionValuesResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_dimensions', {"project_id": context.project_id})

        values = await thanos.get_label_values(
            label_name=dimension_name,
            metric_name=name,
        )

        return metric_schemas.DimensionValuesResponse(
            dimension_name=dimension_name,
            dimension_values=sorted(values),
            message="Dimension values fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_dimension_values: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/hosts",
    description="List hosts sending metrics (admin only)",
    responses={
        200: {"model": metric_schemas.HostListResponse},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.HostListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_hosts(
    request: Request,
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.HostListResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_hosts', {})

        series = await thanos.get_series(match="node_uname_info")
        hosts = _format_hosts(series)

        return metric_schemas.HostListResponse(
            elements=[metric_schemas.HostElement(**h) for h in hosts],
            message="Hosts fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_hosts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/vms",
    description="List VMs sending metrics (admin sees all, tenant sees own)",
    responses={
        200: {"model": metric_schemas.VMListResponse},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.VMListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_vms(
    request: Request,
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.VMListResponse:
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
            policy.authorize(context, 'metric:get_vms', {"project_id": project_id})

        # Thanos'tan VM serilerini cek
        match_query = "libvirt_domain_info_virtual_cpus"
        if not is_admin and project_id:
            match_query = f'libvirt_domain_info_virtual_cpus{{project_id="{project_id}"}}'

        series = await thanos.get_series(match=match_query)
        vms = _format_vms(series)

        return metric_schemas.VMListResponse(
            elements=[metric_schemas.VMElement(**vm) for vm in vms],
            message="VMs fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_vms: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
