import pytest
from datetime import datetime, timedelta


def _make_daily_usages(days=30, base_value=50, growth=0.3):
    """Test icin yapay gunluk veri uretir."""
    base = datetime.now() - timedelta(days=days)
    return [
        [(base + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z"), base_value + i * growth]
        for i in range(days)
    ]


@pytest.mark.asyncio
class TestProphetForecaster:
    async def test_initialization_with_valid_data(self):
        from safir_monitoring.common.prophet_forecaster import ProphetForecaster

        base = datetime.now() - timedelta(days=30)
        daily_usages = [
            [(base + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z"), 40 + i * 0.5]
            for i in range(30)
        ]

        forecaster = ProphetForecaster(daily_usages, total_capacity=100, future_days=30)
        assert forecaster.total_capacity == 100
        assert len(forecaster.df) == 30

    async def test_get_daily_growth_increasing(self):
        from safir_monitoring.common.prophet_forecaster import ProphetForecaster

        base = datetime.now() - timedelta(days=30)
        daily_usages = [
            [(base + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z"), 40 + i * 1.0]
            for i in range(30)
        ]

        forecaster = ProphetForecaster(daily_usages, total_capacity=100, future_days=30)
        growth = forecaster.get_daily_growth()
        assert growth > 0

    async def test_prediction_result_structure(self):
        from safir_monitoring.common.prophet_forecaster import ProphetForecaster

        base = datetime.now() - timedelta(days=30)
        daily_usages = [
            [(base + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z"), 50 + i * 0.3]
            for i in range(30)
        ]

        forecaster = ProphetForecaster(daily_usages, total_capacity=100, future_days=30)
        result = forecaster.get_prediction_result("cpu")

        assert "status" in result
        assert "current_usage" in result
        assert "total_capacity" in result
        assert "usage_percentage" in result
        assert "daily_growth" in result
        assert "resource_type" in result
        assert result["resource_type"] == "cpu"
        assert result["total_capacity"] == 100

    async def test_trend_graph_result_structure(self):
        from safir_monitoring.common.prophet_forecaster import ProphetForecaster

        base = datetime.now() - timedelta(days=30)
        daily_usages = [
            [(base + timedelta(days=i)).strftime("%Y-%m-%dT00:00:00Z"), 50 + i * 0.3]
            for i in range(30)
        ]

        forecaster = ProphetForecaster(daily_usages, total_capacity=100, future_days=30)
        result = forecaster.get_trend_graph_result("cpu", dimension="host1")

        assert "data_points" in result
        assert "future_predictions" in result
        assert "statistics" in result
        assert "capacity_line" in result
        assert result["dimension"] == "host1"
        assert len(result["data_points"]) == 30
        assert len(result["future_predictions"]) == 30


@pytest.mark.asyncio
class TestArimaForecaster:
    async def test_initialization_with_valid_data(self):
        from safir_monitoring.common.arima_forecaster import ArimaForecaster

        daily_usages = _make_daily_usages(days=30, base_value=40, growth=0.5)
        forecaster = ArimaForecaster(daily_usages, total_capacity=100, future_days=30)

        assert forecaster.total_capacity == 100
        assert len(forecaster.df) == 30
        assert forecaster.ALGORITHM_NAME == "arima"

    async def test_prediction_result_structure(self):
        from safir_monitoring.common.arima_forecaster import ArimaForecaster

        daily_usages = _make_daily_usages(days=30, base_value=50, growth=0.3)
        forecaster = ArimaForecaster(daily_usages, total_capacity=100, future_days=30)
        result = forecaster.get_prediction_result("cpu")

        assert "status" in result
        assert "current_usage" in result
        assert "total_capacity" in result
        assert result["resource_type"] == "cpu"
        assert result["total_capacity"] == 100

    async def test_trend_graph_result_structure(self):
        from safir_monitoring.common.arima_forecaster import ArimaForecaster

        daily_usages = _make_daily_usages(days=30, base_value=50, growth=0.3)
        forecaster = ArimaForecaster(daily_usages, total_capacity=100, future_days=30)
        result = forecaster.get_trend_graph_result("cpu", dimension="host1")

        assert "data_points" in result
        assert "future_predictions" in result
        assert "statistics" in result
        assert result["dimension"] == "host1"
        assert len(result["data_points"]) == 30
        assert len(result["future_predictions"]) == 30

    async def test_forecast_dataframe_has_required_columns(self):
        from safir_monitoring.common.arima_forecaster import ArimaForecaster

        daily_usages = _make_daily_usages(days=30, base_value=40, growth=0.5)
        forecaster = ArimaForecaster(daily_usages, total_capacity=100, future_days=30)

        for col in ['ds', 'yhat', 'yhat_upper', 'yhat_lower', 'trend']:
            assert col in forecaster.forecast.columns


@pytest.mark.asyncio
class TestForecasterFactory:
    async def test_get_prophet(self):
        from safir_monitoring.api.v1.metric_forecasting import _get_forecaster
        from safir_monitoring.common.prophet_forecaster import ProphetForecaster

        daily_usages = _make_daily_usages()
        forecaster = _get_forecaster("prophet", daily_usages, 100, 30)
        assert isinstance(forecaster, ProphetForecaster)

    async def test_get_arima(self):
        from safir_monitoring.api.v1.metric_forecasting import _get_forecaster
        from safir_monitoring.common.arima_forecaster import ArimaForecaster

        daily_usages = _make_daily_usages()
        forecaster = _get_forecaster("arima", daily_usages, 100, 30)
        assert isinstance(forecaster, ArimaForecaster)
