import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
class TestResourceQueryBuilder:
    async def test_build_host_cpu_query(self):
        from safir_monitoring.common.resource_queries import build_host_query
        q = build_host_query("cpu", "10.0.0.1:9100")
        assert 'instance="10.0.0.1:9100"' in q
        assert "safir_host_cpu_usage_percent" in q

    async def test_build_vm_query_with_project(self):
        from safir_monitoring.common.resource_queries import build_vm_query
        q = build_vm_query("cpu", project_id="proj-1")
        assert 'project_id="proj-1"' in q
        assert "libvirt_domain_cpu_utilization_perc" in q

    async def test_build_host_capacity_cpu_is_100(self):
        from safir_monitoring.common.resource_queries import build_host_capacity_query
        cap = build_host_capacity_query("cpu")
        assert cap == 100

    async def test_build_host_capacity_memory_is_query(self):
        from safir_monitoring.common.resource_queries import build_host_capacity_query
        cap = build_host_capacity_query("memory", "10.0.0.1:9100")
        assert isinstance(cap, str)
        assert "node_memory_MemTotal_bytes" in cap
