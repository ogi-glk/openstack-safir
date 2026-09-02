import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_thanos_result(metric_name, labels, values):
    """Thanos query_range sonucu olusturur"""
    metric_labels = {"__name__": metric_name}
    metric_labels.update(labels)
    return {"metric": metric_labels, "values": values}


@pytest.mark.asyncio
class TestMeasurementsEndpoint:
    async def test_measurements_builds_correct_response_admin(self):
        """Admin icin hostname dimensions'ta gorunur"""
        from safir_monitoring.api.v1.metric import _format_measurements

        thanos_result = [
            _make_thanos_result(
                "cpu_usage_active",
                {"hostname": "host1"},
                [[1719014400, "65.3"], [1719014700, "67.1"]]
            )
        ]

        result = _format_measurements("cpu_usage_active", thanos_result, is_admin=True)

        assert len(result) == 1
        assert result[0]["name"] == "cpu_usage_active"
        assert result[0]["dimensions"] == {"hostname": "host1"}
        assert result[0]["measurements"] == [["2024-06-22T00:00:00Z", "65.3"], ["2024-06-22T00:05:00Z", "67.1"]]

    async def test_measurements_hides_hostname_for_tenant(self):
        """Tenant icin hostname dimensions'tan gizlenir"""
        from safir_monitoring.api.v1.metric import _format_measurements

        thanos_result = [
            _make_thanos_result(
                "cpu_usage_active",
                {"hostname": "host1", "job": "node"},
                [[1719014400, "65.3"]]
            )
        ]

        result = _format_measurements("cpu_usage_active", thanos_result, is_admin=False)

        assert "hostname" not in result[0]["dimensions"]
        assert "__name__" not in result[0]["dimensions"]
        assert result[0]["dimensions"] == {"job": "node"}

    async def test_measurements_filters_internal_labels(self):
        """__name__ gibi internal label'lar dimensions'tan cikarilir"""
        from safir_monitoring.api.v1.metric import _format_measurements

        thanos_result = [
            _make_thanos_result(
                "cpu_usage_active",
                {"hostname": "host1", "job": "node"},
                [[1719014400, "65.3"]]
            )
        ]

        result = _format_measurements("cpu_usage_active", thanos_result, is_admin=True)

        assert "__name__" not in result[0]["dimensions"]
        assert result[0]["dimensions"] == {"hostname": "host1", "job": "node"}

    async def test_measurements_empty_result(self):
        """Bos Thanos sonucu bos liste doner"""
        from safir_monitoring.api.v1.metric import _format_measurements

        result = _format_measurements("cpu_usage_active", [])
        assert result == []


@pytest.mark.asyncio
class TestStatisticsFormatting:
    async def test_format_statistics_avg(self):
        """avg istatistigi dogru hesaplanir"""
        from safir_monitoring.api.v1.metric import _compute_statistics

        values = [[1719014400, "60.0"], [1719014700, "70.0"], [1719015000, "80.0"]]
        result = _compute_statistics(values, ["avg"])

        assert len(result) == 1
        assert result[0][0] == 1719014400  # ilk timestamp
        assert abs(result[0][1] - 70.0) < 0.01  # avg

    async def test_format_statistics_all(self):
        """Tum istatistikler dogru hesaplanir"""
        from safir_monitoring.api.v1.metric import _compute_statistics

        values = [[1719014400, "10.0"], [1719014700, "20.0"], [1719015000, "30.0"]]
        result = _compute_statistics(values, ["avg", "min", "max", "count", "sum"])

        assert len(result) == 1
        row = result[0]
        assert row[0] == 1719014400  # timestamp
        assert abs(row[1] - 20.0) < 0.01  # avg
        assert abs(row[2] - 10.0) < 0.01  # min
        assert abs(row[3] - 30.0) < 0.01  # max
        assert row[4] == 3  # count
        assert abs(row[5] - 60.0) < 0.01  # sum

    async def test_format_statistics_with_period(self):
        """Period verildiginde zaman dilimlerine bolunur"""
        from safir_monitoring.api.v1.metric import _compute_statistics

        values = [
            [1719014400, "10.0"],
            [1719014700, "20.0"],
            [1719015000, "30.0"],
            [1719015300, "40.0"],
            [1719015600, "50.0"],
            [1719015900, "60.0"],
        ]
        result = _compute_statistics(values, ["avg"], period=600)

        assert len(result) == 3
        assert abs(result[0][1] - 15.0) < 0.01  # avg of 10, 20
        assert abs(result[1][1] - 35.0) < 0.01  # avg of 30, 40
        assert abs(result[2][1] - 55.0) < 0.01  # avg of 50, 60

    async def test_format_statistics_empty(self):
        """Bos values listesi bos sonuc doner"""
        from safir_monitoring.api.v1.metric import _compute_statistics

        result = _compute_statistics([], ["avg"])
        assert result == []
