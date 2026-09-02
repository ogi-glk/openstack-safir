import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
class TestTopNHostFormatting:
    async def test_format_top_n_host_with_nodename_map(self):
        from safir_monitoring.api.v1.metric_operations import _format_top_n_host

        thanos_result = [
            {
                "metric": {"instance": "10.0.0.1:9100"},
                "values": [[1719014400, "95.2"], [1719014700, "96.1"]],
            },
            {
                "metric": {"instance": "10.0.0.2:9100"},
                "values": [[1719014400, "87.5"], [1719014700, "88.3"]],
            },
        ]
        nodename_map = {
            "10.0.0.1:9100": "compute-01",
            "10.0.0.2:9100": "compute-02",
        }

        result = _format_top_n_host(thanos_result, "avg", nodename_map)

        assert len(result) == 2
        assert result[0]["hostname"] == "compute-01"
        assert abs(result[0]["value"] - 95.65) < 0.01
        assert result[1]["hostname"] == "compute-02"

    async def test_format_top_n_host_without_nodename_map(self):
        from safir_monitoring.api.v1.metric_operations import _format_top_n_host

        thanos_result = [
            {
                "metric": {"instance": "10.0.0.1:9100"},
                "values": [[1719014400, "50.0"]],
            },
        ]

        result = _format_top_n_host(thanos_result, "avg")
        assert result[0]["hostname"] == "10.0.0.1:9100"

    async def test_format_top_n_host_empty(self):
        from safir_monitoring.api.v1.metric_operations import _format_top_n_host

        assert _format_top_n_host([], "avg") == []


@pytest.mark.asyncio
class TestTopNVMFormatting:
    async def test_format_top_n_vm_admin(self):
        from safir_monitoring.api.v1.metric_operations import _format_top_n_vm

        thanos_result = [
            {
                "metric": {
                    "__name__": "libvirt_domain_cpu_utilization_perc",
                    "instance_name": "web-1",
                    "instance_id": "id-1",
                    "project_id": "proj-1",
                    "hostname": "compute-01",
                },
                "values": [[1719014400, "90.0"], [1719014700, "80.0"]],
            },
            {
                "metric": {
                    "__name__": "libvirt_domain_cpu_utilization_perc",
                    "instance_name": "db-1",
                    "instance_id": "id-2",
                    "project_id": "proj-1",
                    "hostname": "compute-02",
                },
                "values": [[1719014400, "50.0"], [1719014700, "60.0"]],
            },
        ]

        result = _format_top_n_vm(thanos_result, "avg", is_admin=True)

        assert len(result) == 2
        assert result[0]["vm_name"] == "web-1"
        assert result[0]["hostname"] == "compute-01"
        assert abs(result[0]["value"] - 85.0) < 0.01

    async def test_format_top_n_vm_tenant_hides_hostname(self):
        from safir_monitoring.api.v1.metric_operations import _format_top_n_vm

        thanos_result = [
            {
                "metric": {
                    "instance_name": "web-1",
                    "instance_id": "id-1",
                    "project_id": "proj-1",
                    "hostname": "compute-01",
                },
                "values": [[1719014400, "90.0"]],
            },
        ]

        result = _format_top_n_vm(thanos_result, "avg", is_admin=False)

        assert result[0]["hostname"] == ""
        assert "hostname" not in result[0]["dimensions"]


@pytest.mark.asyncio
class TestWoWChangeCalculation:
    async def test_compute_wow_change(self):
        from safir_monitoring.api.v1.metric_operations import _compute_wow_change

        current = [
            {
                "metric": {"hostname": "host1", "instance": "10.0.0.1:9100"},
                "values": [[1, "70.0"], [2, "80.0"]],
            }
        ]
        previous = [
            {
                "metric": {"hostname": "host1", "instance": "10.0.0.1:9100"},
                "values": [[1, "60.0"], [2, "70.0"]],
            }
        ]

        result = _compute_wow_change(current, previous, "avg", is_admin=True)

        assert len(result) == 1
        assert abs(result[0]["current_week_value"] - 75.0) < 0.01
        assert abs(result[0]["previous_week_value"] - 65.0) < 0.01
        assert abs(result[0]["change"] - 10.0) < 0.01
        assert abs(result[0]["change_percent"] - 15.38) < 0.1

    async def test_compute_wow_change_zero_previous(self):
        from safir_monitoring.api.v1.metric_operations import _compute_wow_change

        current = [
            {
                "metric": {"hostname": "host1"},
                "values": [[1, "50.0"]],
            }
        ]
        previous = [
            {
                "metric": {"hostname": "host1"},
                "values": [[1, "0.0"]],
            }
        ]

        result = _compute_wow_change(current, previous, "avg", is_admin=True)

        assert result[0]["change_percent"] is None

    async def test_compute_wow_change_empty(self):
        from safir_monitoring.api.v1.metric_operations import _compute_wow_change

        result = _compute_wow_change([], [], "avg", is_admin=True)
        assert result == []

    async def test_compute_wow_change_tenant_hides_hostname(self):
        from safir_monitoring.api.v1.metric_operations import _compute_wow_change

        current = [
            {
                "metric": {"hostname": "host1", "job": "node"},
                "values": [[1, "70.0"]],
            }
        ]
        previous = [
            {
                "metric": {"hostname": "host1", "job": "node"},
                "values": [[1, "60.0"]],
            }
        ]

        result = _compute_wow_change(current, previous, "avg", is_admin=False)

        assert "hostname" not in result[0]["dimensions"]
