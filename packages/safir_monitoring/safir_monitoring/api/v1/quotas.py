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

from typing import List, Dict
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_log import log as logging

from safir_monitoring.schemas import quotas as quota_schemas
from safir_monitoring.common import policy, utils, thanos


LOG = logging.getLogger(__name__)

router = APIRouter()


def format_value(value: str) -> str:
    try:
        f = float(value)
        return str(int(f)) if f == int(f) else f"{f:.2f}"
    except (ValueError, TypeError):
        return str(value)


async def get_project_quota(project_id: str) -> quota_schemas.QuotaResponse:
    LOG.debug(f"Fetching quotas for project_id={project_id}")
    
    # VCPU quota
    vcpu_used = await thanos.execute_instant_query(
        f'openstack_nova_limits_vcpus_used{{tenant_id="{project_id}"}}'
    )
    vcpu_max = await thanos.execute_instant_query(
        f'openstack_nova_limits_vcpus_max{{tenant_id="{project_id}"}}'
    )
    vcpu_percent = (float(vcpu_used) / float(vcpu_max) * 100) if float(vcpu_max) > 0 else 0
    
    # Memory quota (MB -> GB)
    memory_used_mb = await thanos.execute_instant_query(
        f'openstack_nova_limits_memory_used{{tenant_id="{project_id}"}}'
    )
    memory_max_mb = await thanos.execute_instant_query(
        f'openstack_nova_limits_memory_max{{tenant_id="{project_id}"}}'
    )
    memory_used_gb = float(memory_used_mb) / 1024
    memory_max_gb = float(memory_max_mb) / 1024
    memory_percent = (memory_used_gb / memory_max_gb * 100) if memory_max_gb > 0 else 0
    
    # Disk quota
    disk_used = await thanos.execute_instant_query(
        f'openstack_cinder_limits_volume_used_gb{{tenant_id="{project_id}"}}'
    )
    disk_max = await thanos.execute_instant_query(
        f'openstack_cinder_limits_volume_max_gb{{tenant_id="{project_id}"}}'
    )
    disk_percent = (float(disk_used) / float(disk_max) * 100) if float(disk_max) > 0 else 0
    
    # Instance quota
    instance_used = await thanos.execute_instant_query(
        f'openstack_nova_limits_instances_used{{tenant_id="{project_id}"}}'
    )
    instance_max = await thanos.execute_instant_query(
        f'openstack_nova_limits_instances_max{{tenant_id="{project_id}"}}'
    )
    instance_percent = (float(instance_used) / float(instance_max) * 100) if float(instance_max) > 0 else 0
    
    # Format values
    vcpu_used_str = format_value(vcpu_used)
    vcpu_max_str = format_value(vcpu_max)
    instance_used_str = format_value(instance_used)
    instance_max_str = format_value(instance_max)
    disk_used_str = format_value(disk_used)
    disk_max_str = format_value(disk_max)
    
    # Format memory GB values
    memory_used_str = format_value(f"{memory_used_gb:.2f}")
    memory_max_str = format_value(f"{memory_max_gb:.2f}")
    
    return quota_schemas.QuotaResponse(
        instances=quota_schemas.QuotaProgressValue(
            label=f"{instance_used_str}/{instance_max_str} VM",
            percent=round(instance_percent, 2)
        ),
        vcpus=quota_schemas.QuotaProgressValue(
            label=f"{vcpu_used_str}/{vcpu_max_str} Cores",
            percent=round(vcpu_percent, 2)
        ),
        memory=quota_schemas.QuotaProgressValue(
            label=f"{memory_used_str}/{memory_max_str} GB",
            percent=round(memory_percent, 2)
        ),
        disk=quota_schemas.QuotaProgressValue(
            label=f"{disk_used_str}/{disk_max_str} GB",
            percent=round(disk_percent, 2)
        )
    )


async def get_host_quotas_data() -> quota_schemas.HostQuotaResponse:
    LOG.debug("Fetching host quotas")
    
    # === TOPLAM VCPU ===
    total_vcpu_used = await thanos.execute_instant_query(
        'sum(openstack_placement_resource_usage{resourcetype="VCPU"})'
    )
    total_vcpu_max = await thanos.execute_instant_query(
        'sum(openstack_placement_resource_total{resourcetype="VCPU"} '
        '* on(hostname) group_left '
        'openstack_placement_resource_allocation_ratio{resourcetype="VCPU"})'
    )
    total_vcpu_percent = (float(total_vcpu_used) / float(total_vcpu_max) * 100) if float(total_vcpu_max) > 0 else 0
    
    # === TOPLAM MEMORY ===
    total_memory_used = await thanos.execute_instant_query(
        'sum(openstack_placement_resource_usage{resourcetype="MEMORY_MB"})'
    )
    total_memory_max = await thanos.execute_instant_query(
        'sum(openstack_placement_resource_total{resourcetype="MEMORY_MB"} '
        '* on(hostname) group_left '
        'openstack_placement_resource_allocation_ratio{resourcetype="MEMORY_MB"})'
    )
    total_memory_percent = (float(total_memory_used) / float(total_memory_max) * 100) if float(total_memory_max) > 0 else 0
    
    # === HER HOST İÇİN AYRI AYRI ===
    # VCPU per host
    vcpu_per_host_used = await thanos.execute_range_query(
        'openstack_placement_resource_usage{resourcetype="VCPU"}'
    )
    vcpu_per_host_max = await thanos.execute_range_query(
        'openstack_placement_resource_total{resourcetype="VCPU"} '
        '* on(hostname) group_left '
        'openstack_placement_resource_allocation_ratio{resourcetype="VCPU"}'
    )
    
    # Memory per host
    memory_per_host_used = await thanos.execute_range_query(
        'openstack_placement_resource_usage{resourcetype="MEMORY_MB"}'
    )
    memory_per_host_max = await thanos.execute_range_query(
        'openstack_placement_resource_total{resourcetype="MEMORY_MB"} '
        '* on(hostname) group_left '
        'openstack_placement_resource_allocation_ratio{resourcetype="MEMORY_MB"}'
    )
    
    # Hostları organize et
    hosts_data: Dict[str, Dict] = {}
    
    # VCPU used
    for result in vcpu_per_host_used:
        hostname = result.get("metric", {}).get("hostname", "unknown")
        value = result.get("value", ["0", "0"])[1]
        if hostname not in hosts_data:
            hosts_data[hostname] = {}
        hosts_data[hostname]["vcpu_used"] = value
    
    # VCPU max
    for result in vcpu_per_host_max:
        hostname = result.get("metric", {}).get("hostname", "unknown")
        value = result.get("value", ["0", "0"])[1]
        if hostname not in hosts_data:
            hosts_data[hostname] = {}
        hosts_data[hostname]["vcpu_max"] = value
    
    # Memory used
    for result in memory_per_host_used:
        hostname = result.get("metric", {}).get("hostname", "unknown")
        value = result.get("value", ["0", "0"])[1]
        if hostname not in hosts_data:
            hosts_data[hostname] = {}
        hosts_data[hostname]["memory_used"] = value
    
    # Memory max
    for result in memory_per_host_max:
        hostname = result.get("metric", {}).get("hostname", "unknown")
        value = result.get("value", ["0", "0"])[1]
        if hostname not in hosts_data:
            hosts_data[hostname] = {}
        hosts_data[hostname]["memory_max"] = value
    
    # Host listesi oluştur
    hosts = []
    for hostname, data in hosts_data.items():
        vcpu_used = float(data.get("vcpu_used", "0"))
        vcpu_max = float(data.get("vcpu_max", "0"))
        memory_used = float(data.get("memory_used", "0"))
        memory_max = float(data.get("memory_max", "0"))
        
        vcpu_percent = (vcpu_used / vcpu_max * 100) if vcpu_max > 0 else 0
        memory_percent = (memory_used / memory_max * 100) if memory_max > 0 else 0
        
        hosts.append(quota_schemas.HostQuotaItem(
            hostname=hostname,
            vcpus=quota_schemas.QuotaProgressValue(
                label=f"{format_value(str(vcpu_used))}/{format_value(str(vcpu_max))} Cores",
                percent=round(vcpu_percent, 2)
            ),
            memory=quota_schemas.QuotaProgressValue(
                label=f"{format_value(str(memory_used))}/{format_value(str(memory_max))} MB",
                percent=round(memory_percent, 2)
            )
        ))
    
    # Response oluştur
    return quota_schemas.HostQuotaResponse(
        total=quota_schemas.HostQuotaTotal(
            vcpus=quota_schemas.QuotaProgressValue(
                label=f"{format_value(total_vcpu_used)}/{format_value(total_vcpu_max)} Cores",
                percent=round(total_vcpu_percent, 2)
            ),
            memory=quota_schemas.QuotaProgressValue(
                label=f"{format_value(total_memory_used)}/{format_value(total_memory_max)} MB",
                percent=round(total_memory_percent, 2)
            )
        ),
        hosts=hosts
    )


@router.get(
    "/quotas",
    description="Get project quotas for Safir-Bulut platform (policy: admin or owner)",
    responses={
        200: {"model": quota_schemas.QuotaSuccessResponse},
        401: {"model": quota_schemas.UnauthorizedMessage},
        403: {"model": quota_schemas.ForbiddenMessage},
        404: {"model": quota_schemas.NotFoundMessage},
        500: {"model": quota_schemas.InternalServerErrorMessage},
    },
    response_model=quota_schemas.QuotaSuccessResponse,
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def get_quotas(
    request: Request,
    project_id: str = Query(..., description="Project ID"),
    X_Auth_Token: str = Header(default=None)
) -> quota_schemas.QuotaSuccessResponse:
    """
    Bir projenin Safir-Bulut quota bilgilerini döndürür.
    project_id aynı zamanda tenant_id olarak kullanılır.
    """
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'quota:get', {"project_id": project_id})
        
        LOG.info(f"GetQuotas request received for project_id={project_id}")
        
        # Quota bilgilerini al
        quota_data = await get_project_quota(project_id)
        
        LOG.info(f"Successfully fetched quota for project_id={project_id}")
        
        return quota_schemas.QuotaSuccessResponse(
            data=quota_data,
            message="Fetched successfully",
            code=200,
            title="OK"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_quotas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/host_quotas",
    description="Get host-level quotas for Safir-Bulut platform (policy: admin only)",
    responses={
        200: {"model": quota_schemas.HostQuotaSuccessResponse},
        401: {"model": quota_schemas.UnauthorizedMessage},
        403: {"model": quota_schemas.ForbiddenMessage},
        500: {"model": quota_schemas.InternalServerErrorMessage},
    },
    response_model=quota_schemas.HostQuotaSuccessResponse,
    status_code=status.HTTP_200_OK,
    response_description="OK",
)
async def get_host_quotas(
    request: Request,
    X_Auth_Token: str = Header(default=None)
) -> quota_schemas.HostQuotaSuccessResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'quota:get_host', {})
        
        LOG.info("GetHostQuotas request received")
        
        # Host quota bilgilerini al
        host_quota_data = await get_host_quotas_data()
        
        LOG.info(f"Successfully fetched host quotas for {len(host_quota_data.hosts)} hosts")
        
        return quota_schemas.HostQuotaSuccessResponse(
            data=host_quota_data,
            message="Host quotas fetched successfully",
            code=200,
            title="OK"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_host_quotas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )