import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp


def _mock_thanos_session(response_data):
    """Thanos HTTP session mock'u olusturur."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=response_data)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


@pytest.fixture(autouse=True)
def mock_conf():
    """CONF.thanos mock'u — tum testlerde otomatik kullanilir."""
    with patch("safir_monitoring.common.thanos.CONF") as mock:
        mock.thanos.querier_endpoint = "http://localhost:10903"
        yield mock


@pytest.mark.asyncio
class TestGetLabelNames:
    async def test_returns_label_names_for_metric(self):
        mock_session = _mock_thanos_session({
            "status": "success",
            "data": ["__name__", "hostname", "instance", "job"]
        })

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_label_names
            result = await get_label_names(metric_name="cpu_usage_active")

        assert result == ["__name__", "hostname", "instance", "job"]

    async def test_returns_empty_list_on_no_data(self):
        mock_session = _mock_thanos_session({
            "status": "success",
            "data": []
        })

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_label_names
            result = await get_label_names(metric_name="nonexistent")

        assert result == []


@pytest.mark.asyncio
class TestGetLabelValues:
    async def test_returns_values_for_label(self):
        mock_session = _mock_thanos_session({
            "status": "success",
            "data": ["host1", "host2", "host3"]
        })

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_label_values
            result = await get_label_values(label_name="hostname")

        assert result == ["host1", "host2", "host3"]


@pytest.mark.asyncio
class TestGetSeries:
    async def test_returns_series_list(self):
        mock_session = _mock_thanos_session({
            "status": "success",
            "data": [
                {"__name__": "node_uname_info", "nodename": "host1", "instance": "10.0.0.1:9100"},
                {"__name__": "node_uname_info", "nodename": "host2", "instance": "10.0.0.2:9100"},
            ]
        })

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_series
            result = await get_series(match='node_uname_info')

        assert len(result) == 2
        assert result[0]["nodename"] == "host1"
