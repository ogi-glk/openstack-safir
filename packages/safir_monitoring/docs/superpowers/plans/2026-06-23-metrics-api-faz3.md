# Metrics API Faz 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** safir_monitoring servisine Prophet tabanli forecasting (prediction, trend-graph, max-value) ve rightsizing (idle/over/under-provisioned VM) endpoint'lerini eklemek.

**Architecture:** monasca-api'deki `ProphetForecaster` sinifi adapte edilir. Thanos'tan gecmis veri cekilir, Prophet ile tahmin uretilir. Forecasting endpoint'leri `metric_forecasting.py`, rightsizing endpoint'leri `metric_rightsizing.py` dosyalarinda toplanir. Resource type -> PromQL eslestirmesi `resource_queries.py` config dosyasinda merkezi olarak tanimlanir.

**Tech Stack:** FastAPI, Prophet (>=1.1), pandas (>=1.3), aiohttp (Thanos), Pydantic, oslo.policy

---

## Bagimliliklar

`requirements.txt`'e eklenecek:
```
prophet>=1.1
pandas>=1.3.0
```

## Resource Type -> PromQL Eslestirmesi

Her resource_type icin host ve VM bazinda kullanilacak PromQL sorgulari:

| resource_type | Host (node) PromQL | VM (libvirt) PromQL |
|---|---|---|
| `cpu` | `100 - avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100` | `libvirt_domain_cpu_utilization_perc` |
| `memory` | `(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100` | `libvirt_domain_memory_stats_used_percent` |
| `disk` | `(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100` | `libvirt_domain_block_stats_allocation_bytes / libvirt_domain_block_stats_capacity_bytes * 100` |

Kapasite degerleri (total_capacity):
- CPU: `100` (yuzde) veya `count(node_cpu_seconds_total{mode="idle"})` (vCPU sayisi)
- Memory: `node_memory_MemTotal_bytes` (byte)
- Disk: `node_filesystem_size_bytes{mountpoint="/"}` (byte)

Rightsizing icin allocated kaynaklar:
- vCPU: `libvirt_domain_info_virtual_cpus`
- Memory: `libvirt_domain_info_maximum_memory_bytes`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `requirements.txt` | Modify | prophet, pandas bagimliliklari |
| `safir_monitoring/common/resource_queries.py` | Create | Resource type -> PromQL eslestirme config |
| `safir_monitoring/common/prophet_forecaster.py` | Create | ProphetForecaster sinifi (monasca-api'den adapte) |
| `safir_monitoring/schemas/forecasting.py` | Create | Forecasting + rightsizing schemalari |
| `safir_monitoring/common/policies/metric.py` | Modify | Yeni policy kurallari |
| `safir_monitoring/api/v1/metric_forecasting.py` | Create | Forecasting endpoint'leri (6 endpoint) |
| `safir_monitoring/api/v1/metric_rightsizing.py` | Create | Rightsizing endpoint'leri (4 endpoint) |
| `safir_monitoring/api/v1/__init__.py` | Modify | Yeni router'lari kaydet |
| `tests/test_prophet_forecaster.py` | Create | ProphetForecaster unit testleri |
| `tests/test_metric_forecasting.py` | Create | Forecasting endpoint testleri |
| `tests/test_metric_rightsizing.py` | Create | Rightsizing endpoint testleri |

---

### Task 1: Bagimliliklar ve Resource Query Config

**Files:**
- Modify: `requirements.txt`
- Create: `safir_monitoring/common/resource_queries.py`

- [ ] **Step 1: requirements.txt'e prophet ve pandas ekle**

`requirements.txt` sonuna ekle:
```
prophet>=1.1
pandas>=1.3.0
```

- [ ] **Step 2: resource_queries.py olustur**

`safir_monitoring/common/resource_queries.py`:
```python
"""Resource type -> PromQL sorgu eslestirmesi.

Forecasting ve rightsizing endpoint'leri bu config'i kullanir.
"""

# Host (node-exporter) metrikleri — yuzde cinsinden kullanim
HOST_QUERIES = {
    "cpu": '100 - avg by(instance) (rate(node_cpu_seconds_total{{mode="idle"{dim_filter}}}[5m])) * 100',
    "memory": '(1 - node_memory_MemAvailable_bytes{{{dim_filter}}} / node_memory_MemTotal_bytes{{{dim_filter}}}) * 100',
    "disk": '(1 - node_filesystem_avail_bytes{{mountpoint="/"{dim_filter}}} / node_filesystem_size_bytes{{mountpoint="/"{dim_filter}}}) * 100',
}

# Host kapasite sorgulari (total_capacity icin)
HOST_CAPACITY_QUERIES = {
    "cpu": 100,  # Sabit: yuzde olarak 100
    "memory": 'node_memory_MemTotal_bytes{{{dim_filter}}}',
    "disk": 'node_filesystem_size_bytes{{mountpoint="/"{dim_filter}}}',
}

# VM (libvirt-exporter) metrikleri — yuzde cinsinden kullanim
VM_QUERIES = {
    "cpu": 'libvirt_domain_cpu_utilization_perc{{{dim_filter}}}',
    "memory": 'libvirt_domain_memory_stats_used_percent{{{dim_filter}}}',
    "disk": 'libvirt_domain_block_stats_allocation_bytes{{{dim_filter}}} / libvirt_domain_block_stats_capacity_bytes{{{dim_filter}}} * 100',
}

# VM allocated kaynak sorgulari (rightsizing icin)
VM_ALLOCATED_QUERIES = {
    "vcpu": 'libvirt_domain_info_virtual_cpus{{{dim_filter}}}',
    "memory_bytes": 'libvirt_domain_info_maximum_memory_bytes{{{dim_filter}}}',
}

VALID_RESOURCE_TYPES = {"cpu", "memory", "disk"}


def build_host_query(resource_type: str, instance: str = None) -> str:
    """Host icin PromQL sorgusu olusturur."""
    dim_filter = f',instance="{instance}"' if instance else ""
    return HOST_QUERIES[resource_type].format(dim_filter=dim_filter)


def build_host_capacity_query(resource_type: str, instance: str = None):
    """Host kapasite sorgusu olusturur. Sabit deger veya PromQL doner."""
    cap = HOST_CAPACITY_QUERIES[resource_type]
    if isinstance(cap, (int, float)):
        return cap
    dim_filter = f'instance="{instance}"' if instance else ""
    return cap.format(dim_filter=dim_filter)


def build_vm_query(resource_type: str, project_id: str = None, instance_id: str = None) -> str:
    """VM icin PromQL sorgusu olusturur."""
    filters = []
    if project_id:
        filters.append(f'project_id="{project_id}"')
    if instance_id:
        filters.append(f'instance_id="{instance_id}"')
    dim_filter = ",".join(filters)
    return VM_QUERIES[resource_type].format(dim_filter=dim_filter)
```

- [ ] **Step 3: Import dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "from safir_monitoring.common.resource_queries import build_host_query, build_vm_query, VALID_RESOURCE_TYPES; print(build_host_query('cpu', 'host1:9100')); print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt safir_monitoring/common/resource_queries.py
git commit -m "feat: add prophet/pandas deps and resource type PromQL query config"
```

---

### Task 2: ProphetForecaster Sinifi

**Files:**
- Create: `safir_monitoring/common/prophet_forecaster.py`
- Create: `tests/test_prophet_forecaster.py`

- [ ] **Step 1: Failing test yaz**

`tests/test_prophet_forecaster.py`:
```python
import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
class TestProphetForecaster:
    async def test_initialization_with_valid_data(self):
        from safir_monitoring.common.prophet_forecaster import ProphetForecaster

        # 30 gunluk yapay veri (artan trend)
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
```

- [ ] **Step 2: Testin fail ettigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_prophet_forecaster.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: ProphetForecaster olustur**

`safir_monitoring/common/prophet_forecaster.py`:
```python
"""Prophet tabanli kapasite tahmin modulu.

monasca-api ProphetForecaster sinifinin Thanos uyumlu adaptasyonu.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
from prophet import Prophet
from oslo_log import log

LOG = log.getLogger(__name__)

# Prophet ve cmdstanpy verbose loglarini sustur
logging.getLogger('prophet').setLevel(logging.WARNING)
logging.getLogger('cmdstanpy').setLevel(logging.WARNING)


class ProphetForecaster:
    """Prophet tabanli kapasite tahmin sinifi.

    Forecasting endpoint'leri tarafindan kullanilir.
    """

    def __init__(self, daily_usages, total_capacity,
                 future_days=90, changepoint_prior_scale=0.05):
        """
        Args:
            daily_usages: [[timestamp_str, value], ...] listesi
                          ornek: [['2026-01-01T00:00:00Z', 42.5], ...]
            total_capacity: float, maksimum kapasite degeri
            future_days: int, kac gun ilerisi tahmin edilecek (default 90)
            changepoint_prior_scale: float, trend degisim hassasiyeti (default 0.05)
        """
        self.total_capacity = float(total_capacity)
        self.future_days = future_days

        self.df = pd.DataFrame({
            'ds': pd.to_datetime(
                [item[0] for item in daily_usages], utc=True
            ).tz_localize(None),
            'y': [float(item[1]) for item in daily_usages]
        })

        self.model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=changepoint_prior_scale
        )
        self.model.fit(self.df)

        future_df = self.model.make_future_dataframe(
            periods=future_days, freq='D')
        self.forecast = self.model.predict(future_df)

        history_len = len(self.df)
        self.historical = self.forecast.iloc[:history_len]
        self.future = self.forecast.iloc[history_len:]

    def get_capacity_full_date(self):
        """Trend'in kapasiteye ulastigi tarihi bulur.

        Returns:
            (datetime, int) veya (None, None)
        """
        future_trend = self.forecast[
            self.forecast['ds'] > self.df['ds'].iloc[-1]]

        exceeds = future_trend[
            future_trend['trend'] >= self.total_capacity]

        if not exceeds.empty:
            full_date = exceeds.iloc[0]['ds'].to_pydatetime()
            days_remaining = (full_date - datetime.now()).days
            if days_remaining > 0:
                return full_date, days_remaining

        trend_vals = self.forecast['trend'].values
        if len(trend_vals) >= 2:
            daily_slope = float(trend_vals[-1] - trend_vals[-2])
            if daily_slope > 0:
                current_trend = float(trend_vals[len(self.df) - 1])
                remaining = self.total_capacity - current_trend
                if remaining > 0:
                    days_remaining = int(remaining / daily_slope)
                    full_date = datetime.now() + timedelta(days=days_remaining)
                    return full_date, days_remaining

        return None, None

    def get_capacity_full_date_upper(self):
        """yhat_upper (worst case) uzerinden kapasite doluluk tarihi."""
        future_data = self.forecast[
            self.forecast['ds'] > self.df['ds'].iloc[-1]]

        exceeds = future_data[
            future_data['yhat_upper'] >= self.total_capacity]

        if not exceeds.empty:
            full_date = exceeds.iloc[0]['ds'].to_pydatetime()
            days_remaining = (full_date - datetime.now()).days
            if days_remaining > 0:
                return full_date, days_remaining

        return None, None

    def get_daily_growth(self):
        """Trend component'inden gunluk buyume oranini hesaplar."""
        hist_len = len(self.df)
        if hist_len >= 2:
            trend_vals = self.forecast['trend'].values
            total_change = float(trend_vals[hist_len - 1] - trend_vals[0])
            return total_change / (hist_len - 1)
        return 0.0

    def get_prediction_result(self, resource_type, extra_fields=None):
        """Prediction API response dict'i olusturur."""
        current_usage = float(self.df['y'].iloc[-1])
        capacity_full_date, days_remaining = self.get_capacity_full_date()
        capacity_full_date_upper, days_remaining_upper = (
            self.get_capacity_full_date_upper())
        daily_growth = self.get_daily_growth()

        if capacity_full_date is None:
            status = "stable"
        elif days_remaining < 90:
            status = "warning"
        else:
            status = "healthy"

        not_applicable = "Trend is stable or decreasing"

        result = {
            "status": status,
            "capacity_full_date": (capacity_full_date.isoformat()
                                   if capacity_full_date else not_applicable),
            "days_remaining": (int(days_remaining)
                               if days_remaining else not_applicable),
            "current_usage": round(current_usage, 2),
            "total_capacity": self.total_capacity,
            "usage_percentage": round(
                (current_usage / self.total_capacity) * 100, 2),
            "daily_growth": round(daily_growth, 4),
            "resource_type": resource_type,
            "prediction_method": "prophet" if capacity_full_date else "none",
            "worst_case": {
                "capacity_full_date": (
                    capacity_full_date_upper.isoformat()
                    if capacity_full_date_upper else not_applicable),
                "days_remaining": (int(days_remaining_upper)
                                   if days_remaining_upper else not_applicable),
            },
            "confidence": {
                "upper": round(
                    float(self.historical['yhat_upper'].iloc[-1]), 2),
                "lower": round(
                    float(self.historical['yhat_lower'].iloc[-1]), 2),
            }
        }

        if status == "stable":
            result["message"] = (
                f"{resource_type} usage is stable or decreasing")

        if extra_fields:
            result.update(extra_fields)

        return result

    def get_trend_graph_result(self, resource_type, dimension=None,
                               unit=None, extra_fields=None):
        """TrendGraph API response dict'i olusturur."""
        current_usage = float(self.df['y'].iloc[-1])
        daily_growth = self.get_daily_growth()
        capacity_full_date, days_remaining = self.get_capacity_full_date()

        data_points = []
        for i in range(len(self.df)):
            row = self.historical.iloc[i]
            data_points.append({
                'date': self.df['ds'].iloc[i].strftime('%Y-%m-%dT00:00:00Z'),
                'actual_value': round(float(self.df['y'].iloc[i]), 4),
                'trend_value': round(float(row['trend']), 4),
                'yhat': round(float(row['yhat']), 4),
                'yhat_upper': round(float(row['yhat_upper']), 4),
                'yhat_lower': round(float(row['yhat_lower']), 4),
            })

        future_predictions = []
        for i in range(len(self.future)):
            row = self.future.iloc[i]
            future_predictions.append({
                'date': row['ds'].strftime('%Y-%m-%dT00:00:00Z'),
                'predicted_value': round(float(row['yhat']), 4),
                'trend_value': round(float(row['trend']), 4),
                'upper_bound': round(float(row['yhat_upper']), 4),
                'lower_bound': round(float(row['yhat_lower']), 4),
            })

        not_applicable = "Trend is stable or decreasing"

        result = {
            'resource_type': resource_type,
            'unit': unit,
            'data_points': data_points,
            'future_predictions': future_predictions,
            'statistics': {
                'current_usage': round(current_usage, 4),
                'total_capacity': self.total_capacity,
                'usage_percentage': round(
                    (current_usage / self.total_capacity) * 100, 2),
                'daily_growth': round(daily_growth, 4),
                'prediction_method': 'prophet',
                'capacity_full_date': (
                    capacity_full_date.isoformat()
                    if capacity_full_date else not_applicable),
                'days_remaining': (
                    int(days_remaining)
                    if days_remaining else not_applicable),
            },
            'capacity_line': {
                'value': self.total_capacity,
                'label': f'Total {resource_type} Capacity'
            }
        }

        if dimension:
            result['dimension'] = dimension

        if extra_fields:
            result.update(extra_fields)

        return result
```

- [ ] **Step 4: pip install prophet pandas (sunucuda da gerekli)**

Run: `pip3 install prophet pandas`

- [ ] **Step 5: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_prophet_forecaster.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add safir_monitoring/common/prophet_forecaster.py tests/test_prophet_forecaster.py
git commit -m "feat: add ProphetForecaster class adapted from monasca-api"
```

---

### Task 3: Forecasting Schemalari

**Files:**
- Create: `safir_monitoring/schemas/forecasting.py`

- [ ] **Step 1: Schemalari olustur**

`safir_monitoring/schemas/forecasting.py`:
```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# ============================================================================
# PREDICTION SCHEMAS
# ============================================================================

class PredictionWorstCase(BaseModel):
    capacity_full_date: Any = Field(..., description="Worst case capacity full date (ISO or message)")
    days_remaining: Any = Field(..., description="Worst case days remaining (int or message)")


class PredictionConfidence(BaseModel):
    upper: float = Field(..., description="Upper confidence bound")
    lower: float = Field(..., description="Lower confidence bound")


class PredictionResponse(BaseModel):
    status: str = Field(..., description="Status: stable, warning, healthy")
    capacity_full_date: Any = Field(..., description="Capacity full date (ISO or message)")
    days_remaining: Any = Field(..., description="Days remaining (int or message)")
    current_usage: float = Field(..., description="Current usage value")
    total_capacity: float = Field(..., description="Total capacity")
    usage_percentage: float = Field(..., description="Usage percentage")
    daily_growth: float = Field(..., description="Daily growth rate")
    resource_type: str = Field(..., description="Resource type (cpu/memory/disk)")
    prediction_method: str = Field(..., description="Method used: prophet or none")
    worst_case: PredictionWorstCase = Field(..., description="Worst case scenario")
    confidence: PredictionConfidence = Field(..., description="Confidence interval")
    dimension: Optional[str] = Field(None, description="Host or VM identifier")
    scope: Optional[str] = Field(None, description="system (for system-wide predictions)")
    message: Optional[str] = Field(None, description="Status message")


class SystemReportResource(BaseModel):
    status: str = Field(...)
    current_usage: float = Field(...)
    total_capacity: float = Field(...)
    usage_percentage: float = Field(...)
    daily_growth: float = Field(...)
    capacity_full_date: Any = Field(...)
    days_remaining: Any = Field(...)


class SystemReportResponse(BaseModel):
    report: Dict[str, SystemReportResource] = Field(..., description="CPU, memory, disk predictions")
    period_days: int = Field(..., description="Forecast period in days")


# ============================================================================
# TREND GRAPH SCHEMAS
# ============================================================================

class TrendDataPoint(BaseModel):
    date: str = Field(...)
    actual_value: float = Field(...)
    trend_value: float = Field(...)
    yhat: float = Field(...)
    yhat_upper: float = Field(...)
    yhat_lower: float = Field(...)


class TrendFuturePrediction(BaseModel):
    date: str = Field(...)
    predicted_value: float = Field(...)
    trend_value: float = Field(...)
    upper_bound: float = Field(...)
    lower_bound: float = Field(...)


class TrendStatistics(BaseModel):
    current_usage: float = Field(...)
    total_capacity: float = Field(...)
    usage_percentage: float = Field(...)
    daily_growth: float = Field(...)
    prediction_method: str = Field(...)
    capacity_full_date: Any = Field(...)
    days_remaining: Any = Field(...)


class TrendCapacityLine(BaseModel):
    value: float = Field(...)
    label: str = Field(...)


class TrendGraphResponse(BaseModel):
    resource_type: str = Field(...)
    unit: Optional[str] = Field(None)
    dimension: Optional[str] = Field(None)
    scope: Optional[str] = Field(None)
    data_points: List[TrendDataPoint] = Field(...)
    future_predictions: List[TrendFuturePrediction] = Field(...)
    statistics: TrendStatistics = Field(...)
    capacity_line: TrendCapacityLine = Field(...)


# ============================================================================
# MAX VALUE SCHEMA
# ============================================================================

class MaxValueResponse(BaseModel):
    resource_type: str = Field(...)
    dimension: str = Field(...)
    current_max: float = Field(...)
    predicted_max: float = Field(...)
    period_days: int = Field(...)


# ============================================================================
# RIGHTSIZING SCHEMAS
# ============================================================================

class RightsizingVMElement(BaseModel):
    instance_id: str = Field(...)
    name: str = Field(...)
    project_id: str = Field(default="")
    hostname: str = Field(default="")
    avg_cpu: Optional[float] = Field(None)
    avg_memory: Optional[float] = Field(None)
    max_cpu: Optional[float] = Field(None)
    max_memory: Optional[float] = Field(None)
    allocated_vcpu: Optional[int] = Field(None)
    allocated_memory_gb: Optional[float] = Field(None)
    recommendation: Optional[Dict[str, Any]] = Field(None)


class RightsizingListResponse(BaseModel):
    vms: List[RightsizingVMElement] = Field(...)
    total_count: int = Field(...)
    period_days: int = Field(...)
    message: str = Field(...)
    code: int = Field(200)
    title: str = Field("OK")


class RightsizingSummary(BaseModel):
    total_vms: int = Field(...)
    idle: int = Field(...)
    over_provisioned: int = Field(...)
    under_provisioned: int = Field(...)
    right_sized: int = Field(...)


class PotentialSavings(BaseModel):
    vcpu: int = Field(...)
    memory_gb: float = Field(...)


class RightsizingReportResponse(BaseModel):
    summary: RightsizingSummary = Field(...)
    idle_vms: List[RightsizingVMElement] = Field(...)
    over_provisioned_vms: List[RightsizingVMElement] = Field(...)
    under_provisioned_vms: List[RightsizingVMElement] = Field(...)
    potential_savings: PotentialSavings = Field(...)
    period_days: int = Field(...)
    message: str = Field("Rightsizing report generated successfully")
    code: int = Field(200)
    title: str = Field("OK")
```

- [ ] **Step 2: Import dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "from safir_monitoring.schemas.forecasting import PredictionResponse, TrendGraphResponse, MaxValueResponse, RightsizingReportResponse; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/schemas/forecasting.py
git commit -m "feat: add Pydantic schemas for forecasting and rightsizing endpoints"
```

---

### Task 4: Policy Kurallari

**Files:**
- Modify: `safir_monitoring/common/policies/metric.py`

- [ ] **Step 1: 10 yeni policy kurali ekle**

`metric_policies` listesine ekle:
```python
    # Forecasting
    policy.DocumentedRuleDefault(
        name='metric:get_prediction',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get resource prediction (owner or admin)',
        operations=[{'path': '/metrics/forecasts/prediction', 'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_prediction_system',
        check_str=base.ROLE_ADMIN,
        description='Get system-wide prediction (admin only)',
        operations=[{'path': '/metrics/forecasts/prediction/system', 'method': 'GET'},
                   {'path': '/metrics/forecasts/prediction/system/report', 'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_trend_graph',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get trend graph data (owner or admin)',
        operations=[{'path': '/metrics/forecasts/trend-graph', 'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_trend_graph_system',
        check_str=base.ROLE_ADMIN,
        description='Get system-wide trend graph (admin only)',
        operations=[{'path': '/metrics/forecasts/trend-graph/system', 'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_max_value',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get predicted max value (owner or admin)',
        operations=[{'path': '/metrics/forecasts/max-value', 'method': 'GET'}],
    ),
    # Rightsizing
    policy.DocumentedRuleDefault(
        name='metric:get_rightsizing',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get rightsizing reports (owner or admin)',
        operations=[{'path': '/metrics/rightsizing/idle-vms', 'method': 'GET'},
                   {'path': '/metrics/rightsizing/over-provisioned-vms', 'method': 'GET'},
                   {'path': '/metrics/rightsizing/under-provisioned-vms', 'method': 'GET'},
                   {'path': '/metrics/rightsizing/report', 'method': 'GET'}],
    ),
```

- [ ] **Step 2: Dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "from safir_monitoring.common.policies.metric import list_rules; print(f'{len(list(list_rules()))} rules')"`
Expected: "17 rules"

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/common/policies/metric.py
git commit -m "feat: add policy rules for forecasting and rightsizing endpoints"
```

---

### Task 5: Forecasting Endpoint'leri

**Files:**
- Create: `safir_monitoring/api/v1/metric_forecasting.py`
- Create: `tests/test_metric_forecasting.py`

Bu dosya 6 endpoint icerir:
1. `GET /metrics/forecasts/prediction` — host/VM bazinda tahmin
2. `GET /metrics/forecasts/prediction/system` — sistem geneli tahmin
3. `GET /metrics/forecasts/prediction/system/report` — CPU+memory+disk raporu
4. `GET /metrics/forecasts/trend-graph` — host/VM bazinda trend grafigi
5. `GET /metrics/forecasts/trend-graph/system` — sistem geneli trend grafigi
6. `GET /metrics/forecasts/max-value` — tahmini maksimum deger

Her endpoint:
- `resource_type` parametresi alir (cpu/memory/disk)
- `resource_queries.py`'den uygun PromQL'i secer
- Thanos'tan 90 gunluk gecmis veriyi cekmek icin `execute_range_query_with_time` kullanir (step=1d)
- `ProphetForecaster` ile tahmin uretir
- Host endpoint'lerinde `node_uname_info`'dan nodename resolve yapar

**Not:** Bu task buyuk oldugu icin implementasyon detaylari dosya icinde olacak, plandaki diger task'lar gibi her satiri burada yazmak yerine dosyanin tam icerigi bir seferde yazilacak.

- [ ] **Step 1: Test yaz**

`tests/test_metric_forecasting.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
class TestResourceQueryBuilder:
    async def test_build_host_cpu_query(self):
        from safir_monitoring.common.resource_queries import build_host_query
        q = build_host_query("cpu", "10.0.0.1:9100")
        assert 'instance="10.0.0.1:9100"' in q
        assert "node_cpu_seconds_total" in q

    async def test_build_vm_query_with_project(self):
        from safir_monitoring.common.resource_queries import build_vm_query
        q = build_vm_query("cpu", project_id="proj-1")
        assert 'project_id="proj-1"' in q
        assert "libvirt_domain_cpu_utilization_perc" in q

    async def test_build_host_capacity_cpu_is_100(self):
        from safir_monitoring.common.resource_queries import build_host_capacity_query
        cap = build_host_capacity_query("cpu")
        assert cap == 100
```

- [ ] **Step 2: metric_forecasting.py olustur**

Dosya icerik ozeti (tam kod implementasyonda yazilacak):
- Her endpoint icin: auth check, resource_type validasyonu, Thanos sorgusu, Prophet calistirma, response dondurme
- `_fetch_daily_data(query, days)`: Thanos'tan gunluk veri ceker (step=1d)
- `_get_total_capacity(resource_type, instance)`: Kapasite degerini alir
- prediction/system: tum instance'lari avg by(instance) ile aggregate eder
- prediction/system/report: asyncio.gather ile CPU+memory+disk paralel calistirir
- max-value: Prophet upper bound'dan predicted_max hesaplar

- [ ] **Step 3: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_metric_forecasting.py -v`

- [ ] **Step 4: Commit**

```bash
git add safir_monitoring/api/v1/metric_forecasting.py tests/test_metric_forecasting.py
git commit -m "feat: add forecasting endpoints (prediction, trend-graph, max-value)"
```

---

### Task 6: Rightsizing Endpoint'leri

**Files:**
- Create: `safir_monitoring/api/v1/metric_rightsizing.py`
- Create: `tests/test_metric_rightsizing.py`

Bu dosya 4 endpoint icerir:
1. `GET /metrics/rightsizing/idle-vms`
2. `GET /metrics/rightsizing/over-provisioned-vms`
3. `GET /metrics/rightsizing/under-provisioned-vms`
4. `GET /metrics/rightsizing/report`

Rightsizing mantigi (monasca-api'den):
- **Idle VM**: CPU avg < %5 VE memory avg < %10 (son N gun — varsayilan 7)
- **Over-provisioned**: max CPU < %30 VE max memory < %30
- **Under-provisioned**: avg CPU > %80 VEYA avg memory > %80

Her VM icin:
1. `libvirt_domain_cpu_utilization_perc` avg ve max
2. `libvirt_domain_memory_stats_used_percent` avg ve max
3. `libvirt_domain_info_virtual_cpus` allocated vCPU
4. `libvirt_domain_info_maximum_memory_bytes` allocated memory

Over/under-provisioned recommendation hesaplama:
- Over: allocated * (max_usage / threshold) ile onerilen kaynak
- Under: allocated * (avg_usage / target_usage) ile onerilen kaynak

- [ ] **Step 1: Test yaz**

`tests/test_metric_rightsizing.py`:
```python
import pytest


@pytest.mark.asyncio
class TestRightsizingClassification:
    async def test_classify_idle_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 2.0, "avg_memory": 5.0, "max_cpu": 3.0, "max_memory": 8.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "idle"

    async def test_classify_over_provisioned_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 15.0, "avg_memory": 20.0, "max_cpu": 25.0, "max_memory": 28.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "over_provisioned"

    async def test_classify_under_provisioned_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 85.0, "avg_memory": 70.0, "max_cpu": 95.0, "max_memory": 80.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "under_provisioned"

    async def test_classify_right_sized_vm(self):
        from safir_monitoring.api.v1.metric_rightsizing import _classify_vm

        vm = {"avg_cpu": 50.0, "avg_memory": 50.0, "max_cpu": 60.0, "max_memory": 55.0}
        result = _classify_vm(vm, cpu_idle=5, mem_idle=10, cpu_over=30, mem_over=30, cpu_under=80, mem_under=80)
        assert result == "right_sized"
```

- [ ] **Step 2: metric_rightsizing.py olustur**

Dosya icerik ozeti:
- `_classify_vm(vm, thresholds)`: VM'i idle/over/under/right_sized olarak siniflandirir
- `_compute_recommendation(vm, category)`: Over/under icin kaynak onerisi hesaplar
- Her endpoint: Thanos'tan VM CPU/memory avg ve max degerlerini cekmek icin paralel sorgular
- report endpoint: tum kategorileri tek seferde hesaplar + potential_savings

- [ ] **Step 3: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_metric_rightsizing.py -v`

- [ ] **Step 4: Commit**

```bash
git add safir_monitoring/api/v1/metric_rightsizing.py tests/test_metric_rightsizing.py
git commit -m "feat: add rightsizing endpoints (idle, over/under-provisioned, report)"
```

---

### Task 7: Route Registration

**Files:**
- Modify: `safir_monitoring/api/v1/__init__.py`

- [ ] **Step 1: Router'lari kaydet**

Import ekle:
```python
from safir_monitoring.api.v1 import metric_forecasting
from safir_monitoring.api.v1 import metric_rightsizing
```

Router registration ekle:
```python
api_router.include_router(metric_forecasting.router, tags=["metric-forecasting"])
api_router.include_router(metric_rightsizing.router, tags=["metric-rightsizing"])
```

- [ ] **Step 2: Route'lari dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "from safir_monitoring.api.v1 import api_router; routes=[r.path for r in api_router.routes if hasattr(r,'path')]; [print(r) for r in sorted(routes) if 'forecast' in r or 'rightsizing' in r]"`

Expected:
```
/metrics/forecasts/max-value
/metrics/forecasts/prediction
/metrics/forecasts/prediction/system
/metrics/forecasts/prediction/system/report
/metrics/forecasts/trend-graph
/metrics/forecasts/trend-graph/system
/metrics/rightsizing/idle-vms
/metrics/rightsizing/over-provisioned-vms
/metrics/rightsizing/report
/metrics/rightsizing/under-provisioned-vms
```

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/api/v1/__init__.py
git commit -m "feat: register forecasting and rightsizing routes"
```

---

### Task 8: Son Dogrulama

- [ ] **Step 1: Tum testleri calistir**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/ -v`
Expected: Tum testler PASS

- [ ] **Step 2: Import chain ve route dogrulamasi**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "
from safir_monitoring.api.v1 import api_router
from safir_monitoring.common.policies.metric import list_rules
print(f'Policy rules: {len(list(list_rules()))}')
routes = [r.path for r in api_router.routes if hasattr(r, 'path')]
print(f'Total routes: {len(routes)}')
faz3 = [r for r in routes if 'forecast' in r or 'rightsizing' in r]
print(f'Faz 3 routes ({len(faz3)}): {faz3}')
"`

Expected:
```
Policy rules: 17
Total routes: 37
Faz 3 routes (10): [...]
```

---

## Ozet

| Task | Dosyalar | Aciklama |
|------|----------|----------|
| 1 | requirements.txt, resource_queries.py | Bagimliliklar + PromQL config |
| 2 | prophet_forecaster.py, test_prophet_forecaster.py | Prophet tahmin sinifi |
| 3 | schemas/forecasting.py | Forecasting + rightsizing schemalari |
| 4 | policies/metric.py | Policy kurallari (6 yeni) |
| 5 | metric_forecasting.py, test_metric_forecasting.py | 6 forecasting endpoint |
| 6 | metric_rightsizing.py, test_metric_rightsizing.py | 4 rightsizing endpoint |
| 7 | __init__.py | Route registration |
| 8 | — | Son dogrulama |

## Notlar

- Prophet model fit islemi CPU-yogun — ilk istek yavas olabilir (~5-10 saniye). Ileride caching eklenebilir.
- Rightsizing esik degerleri query parametresi olarak override edilebilir (varsayilanlar endpoint'te tanimli).
- System-wide endpoint'ler `avg by(instance)` ile aggregate eder, sonra tum instance'larin ortalamasini alir.
- `hostname` bilgisi tenant kullanicilara gizlenir (Faz 1-2 pattern'i korunur).
