import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
class TestFormatHosts:
    async def test_extracts_host_info_from_series(self):
        from safir_monitoring.api.v1.metric_discovery import _format_hosts

        series = [
            {"__name__": "node_uname_info", "nodename": "host1", "instance": "10.0.0.1:9100", "job": "node"},
            {"__name__": "node_uname_info", "nodename": "host2", "instance": "10.0.0.2:9100", "job": "node"},
        ]

        result = _format_hosts(series)

        assert len(result) == 2
        assert result[0]["name"] == "host1"
        assert result[0]["dimensions"]["instance"] == "10.0.0.1:9100"
        assert "__name__" not in result[0]["dimensions"]

    async def test_empty_series_returns_empty(self):
        from safir_monitoring.api.v1.metric_discovery import _format_hosts

        assert _format_hosts([]) == []


@pytest.mark.asyncio
class TestFormatVMs:
    async def test_extracts_vm_info_from_series(self):
        from safir_monitoring.api.v1.metric_discovery import _format_vms

        series = [
            {
                "__name__": "libvirt_domain_info_virtual_cpus",
                "instance_name": "web-server-1",
                "instance_id": "abc-123",
                "project_id": "proj-1",
                "hostname": "compute-01.openstack.local",
                "instance": "10.0.0.1:9177",
            },
        ]

        result = _format_vms(series)

        assert len(result) == 1
        assert result[0]["name"] == "web-server-1"
        assert result[0]["instance_id"] == "abc-123"
        assert result[0]["project_id"] == "proj-1"
        assert result[0]["hostname"] == "compute-01.openstack.local"

    async def test_deduplicates_vms(self):
        from safir_monitoring.api.v1.metric_discovery import _format_vms

        series = [
            {"instance_name": "vm1", "instance_id": "id-1", "project_id": "p1"},
            {"instance_name": "vm1", "instance_id": "id-1", "project_id": "p1"},
        ]

        result = _format_vms(series)
        assert len(result) == 1
