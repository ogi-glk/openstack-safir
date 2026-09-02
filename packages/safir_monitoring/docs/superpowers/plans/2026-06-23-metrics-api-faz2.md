# Metrics API Faz 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** safir_monitoring servisine Top-N Host, Top-N VM ve Week-over-Week Change endpoint'lerini eklemek.

**Architecture:** Yeni endpoint'ler `metric_operations.py` dosyasinda toplanir. Thanos `topk()` PromQL fonksiyonu ve `execute_range_query_with_time` kullanilir. WoW hesaplamasi Python tarafinda yapilir. Faz 1'deki `_filter_dimensions`, `_ts_to_iso`, `_build_query` fonksiyonlari yeniden kullanilir — bunlar `metric.py`'den import edilir.

**Tech Stack:** FastAPI, aiohttp (Thanos client), Pydantic (schemas), oslo.policy (authorization)

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `safir_monitoring/schemas/metrics.py` | Modify | Top-N ve WoW response schemalari ekle |
| `safir_monitoring/common/policies/metric.py` | Modify | top-n ve wow policy kurallari ekle |
| `safir_monitoring/api/v1/metric_operations.py` | Create | top-n-host, top-n-vm, wow-change endpoint'leri |
| `safir_monitoring/api/v1/__init__.py` | Modify | Yeni router'i kaydet |
| `tests/test_metric_operations.py` | Create | Faz 2 endpoint testleri |

---

### Task 1: Pydantic Schemalari

**Files:**
- Modify: `safir_monitoring/schemas/metrics.py`

- [ ] **Step 1: Top-N ve WoW schemalari ekle**

`safir_monitoring/schemas/metrics.py` dosyasinin sonuna ekle:

```python


# ============================================================================
# TOP-N SCHEMAS
# ============================================================================

class TopNHostElement(BaseModel):
    """Top-N host sonucu"""
    hostname: str = Field(..., description="Host name")
    value: float = Field(..., description="Metric value")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Additional labels")


class TopNHostResponse(BaseModel):
    """Top-N host endpoint response"""
    name: str = Field(..., description="Metric name")
    statistic: str = Field(..., description="Statistic used for ranking (avg/max/min)")
    elements: List[TopNHostElement] = Field(..., description="Top N hosts")
    message: str = Field("Top N hosts fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


class TopNVMElement(BaseModel):
    """Top-N VM sonucu"""
    vm_name: str = Field(..., description="VM name")
    instance_id: str = Field(..., description="OpenStack instance ID")
    project_id: str = Field(default="", description="Owner project ID")
    hostname: str = Field(default="", description="Compute host (admin only)")
    value: float = Field(..., description="Metric value")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Additional labels")


class TopNVMResponse(BaseModel):
    """Top-N VM endpoint response"""
    name: str = Field(..., description="Metric name")
    statistic: str = Field(..., description="Statistic used for ranking (avg/max/min)")
    elements: List[TopNVMElement] = Field(..., description="Top N VMs")
    message: str = Field("Top N VMs fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# WOW CHANGE SCHEMAS
# ============================================================================

class WoWChangeElement(BaseModel):
    """Tek bir seri icin Week-over-Week degisim"""
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Series dimensions")
    current_week_value: float = Field(..., description="Current week statistic value")
    previous_week_value: float = Field(..., description="Previous week statistic value")
    change: float = Field(..., description="Absolute change")
    change_percent: Optional[float] = Field(None, description="Percentage change (null if previous is 0)")


class WoWChangeResponse(BaseModel):
    """WoW change endpoint response"""
    name: str = Field(..., description="Metric name")
    statistic: str = Field(..., description="Statistic used (avg/max/min)")
    elements: List[WoWChangeElement] = Field(..., description="Per-series WoW changes")
    message: str = Field("Week-over-week change calculated successfully")
    code: int = Field(200)
    title: str = Field("OK")
```

- [ ] **Step 2: Import'un calistigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "from safir_monitoring.schemas.metrics import TopNHostResponse, TopNVMResponse, WoWChangeResponse; print('OK')"`
Expected: "OK"

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/schemas/metrics.py
git commit -m "feat: add Top-N and WoW change Pydantic schemas for Faz 2"
```

---

### Task 2: Policy Kurallari

**Files:**
- Modify: `safir_monitoring/common/policies/metric.py`

- [ ] **Step 1: Yeni policy kurallarini ekle**

`metric_policies` listesine (son `]`'den once) ekle:

```python
    policy.DocumentedRuleDefault(
        name='metric:get_top_n_host',
        check_str=base.ROLE_ADMIN,
        description='Get top N hosts by metric (admin only)',
        operations=[{'path': '/metrics/statistics/top-n-host',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_top_n_vm',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get top N VMs by metric (owner or admin)',
        operations=[{'path': '/metrics/statistics/top-n-vm',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_wow_change',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get week-over-week change (owner or admin)',
        operations=[{'path': '/metrics/forecasts/wow-change',
                    'method': 'GET'}],
    ),
```

- [ ] **Step 2: Dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "from safir_monitoring.common.policies.metric import list_rules; print(f'{len(list(list_rules()))} rules')"`
Expected: "11 rules"

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/common/policies/metric.py
git commit -m "feat: add policy rules for top-n and wow-change endpoints"
```

---

### Task 3: Top-N Host Endpoint

**Files:**
- Create: `tests/test_metric_operations.py`
- Create: `safir_monitoring/api/v1/metric_operations.py`

- [ ] **Step 1: Failing test yaz**

`tests/test_metric_operations.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
class TestTopNHostFormatting:
    async def test_format_top_n_host(self):
        from safir_monitoring.api.v1.metric_operations import _format_top_n_host

        # Thanos topk sonucu: her seri icin son deger avg olarak kullanilir
        thanos_result = [
            {
                "metric": {"__name__": "node_cpu_seconds_total", "hostname": "host1", "instance": "10.0.0.1:9100"},
                "values": [[1719014400, "95.2"], [1719014700, "96.1"]],
            },
            {
                "metric": {"__name__": "node_cpu_seconds_total", "hostname": "host2", "instance": "10.0.0.2:9100"},
                "values": [[1719014400, "87.5"], [1719014700, "88.3"]],
            },
        ]

        result = _format_top_n_host(thanos_result, "avg")

        assert len(result) == 2
        assert result[0]["hostname"] == "host1"
        assert abs(result[0]["value"] - 95.65) < 0.01  # avg of 95.2, 96.1
        assert result[1]["hostname"] == "host2"

    async def test_format_top_n_host_empty(self):
        from safir_monitoring.api.v1.metric_operations import _format_top_n_host

        assert _format_top_n_host([], "avg") == []
```

- [ ] **Step 2: Testin fail ettigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_metric_operations.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: metric_operations.py olustur (top-n-host)**

`safir_monitoring/api/v1/metric_operations.py`:

```python
from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, Request, HTTPException, status, Query
from oslo_log import log as logging

from safir_monitoring.schemas import metrics as metric_schemas
from safir_monitoring.common import policy, utils, thanos
from safir_monitoring.api.v1.metric import (
    _INTERNAL_LABELS, _filter_dimensions, _ts_to_iso, _build_query, parse_time_to_unix,
)


LOG = logging.getLogger(__name__)

router = APIRouter()

_STAT_FUNCS = {
    "avg": lambda vals: sum(vals) / len(vals) if vals else 0,
    "max": lambda vals: max(vals) if vals else 0,
    "min": lambda vals: min(vals) if vals else 0,
}


def _format_top_n_host(thanos_result: list, statistic: str) -> list:
    """Thanos topk sonucundan host bazli top-n listesi olusturur."""
    func = _STAT_FUNCS.get(statistic, _STAT_FUNCS["avg"])
    hosts = []
    for series in thanos_result:
        labels = series.get("metric", {})
        hostname = labels.get("hostname", labels.get("instance", "unknown"))
        values = [float(v[1]) for v in series.get("values", [])]
        value = func(values)
        dims = {k: v for k, v in labels.items()
                if k not in _INTERNAL_LABELS | {"hostname"}}
        hosts.append({
            "hostname": hostname,
            "value": round(value, 2),
            "dimensions": dims,
        })
    # Degere gore buyukten kucuge sirala
    hosts.sort(key=lambda x: x["value"], reverse=True)
    return hosts


def _format_top_n_vm(thanos_result: list, statistic: str, is_admin: bool) -> list:
    """Thanos topk sonucundan VM bazli top-n listesi olusturur."""
    func = _STAT_FUNCS.get(statistic, _STAT_FUNCS["avg"])
    _vm_extracted = _INTERNAL_LABELS | {"instance_name", "instance_id", "project_id", "hostname", "domain"}
    vms = []
    for series in thanos_result:
        labels = series.get("metric", {})
        values = [float(v[1]) for v in series.get("values", [])]
        value = func(values)
        dims = {k: v for k, v in labels.items() if k not in _vm_extracted}
        if not is_admin:
            dims.pop("hostname", None)
        vm = {
            "vm_name": labels.get("instance_name", labels.get("domain", "unknown")),
            "instance_id": labels.get("instance_id", ""),
            "project_id": labels.get("project_id", ""),
            "hostname": labels.get("hostname", "") if is_admin else "",
            "value": round(value, 2),
            "dimensions": dims,
        }
        vms.append(vm)
    vms.sort(key=lambda x: x["value"], reverse=True)
    return vms


@router.get(
    "/metrics/statistics/top-n-host",
    description="Get top N hosts by metric value (admin only)",
    responses={
        200: {"model": metric_schemas.TopNHostResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.TopNHostResponse,
    status_code=status.HTTP_200_OK,
)
async def get_top_n_host(
    request: Request,
    name: str = Query(..., description="Metric name (e.g., 'node_cpu_seconds_total')"),
    n: int = Query(10, description="Number of results", ge=1, le=100),
    statistic: str = Query("avg", description="Ranking statistic: avg, max, min"),
    start_time: Optional[str] = Query(None, description="Start time ISO format. Default: 1 hour ago"),
    end_time: Optional[str] = Query(None, description="End time ISO format. Default: now"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.TopNHostResponse:
    try:
        context = await utils.req_context_from_scope(request.scope)
        policy.authorize(context, 'metric:get_top_n_host', {})

        if statistic not in _STAT_FUNCS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistic: {statistic}. Valid: avg, max, min"
            )

        now = datetime.now()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

        # topk PromQL: en yuksek N seriyi dondurur
        query = f"topk({n}, {name})"

        LOG.info(f"Top-N Host query: {query}")

        thanos_result = await thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step="60s"
        )

        elements = _format_top_n_host(thanos_result, statistic)[:n]

        return metric_schemas.TopNHostResponse(
            name=name,
            statistic=statistic,
            elements=[metric_schemas.TopNHostElement(**e) for e in elements],
            message="Top N hosts fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_top_n_host: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/metrics/statistics/top-n-vm",
    description="Get top N VMs by metric value (admin sees all, tenant sees own)",
    responses={
        200: {"model": metric_schemas.TopNVMResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.TopNVMResponse,
    status_code=status.HTTP_200_OK,
)
async def get_top_n_vm(
    request: Request,
    name: str = Query(..., description="Metric name (e.g., 'libvirt_domain_cpu_utilization_perc')"),
    n: int = Query(10, description="Number of results", ge=1, le=100),
    statistic: str = Query("avg", description="Ranking statistic: avg, max, min"),
    start_time: Optional[str] = Query(None, description="Start time ISO format. Default: 1 hour ago"),
    end_time: Optional[str] = Query(None, description="End time ISO format. Default: now"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.TopNVMResponse:
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
            policy.authorize(context, 'metric:get_top_n_vm', {"project_id": project_id})

        if statistic not in _STAT_FUNCS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistic: {statistic}. Valid: avg, max, min"
            )

        now = datetime.now()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

        base_query = _build_query(name, project_id if not is_admin else None)
        query = f"topk({n}, {base_query})"

        LOG.info(f"Top-N VM query: {query}")

        thanos_result = await thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step="60s"
        )

        elements = _format_top_n_vm(thanos_result, statistic, is_admin)[:n]

        return metric_schemas.TopNVMResponse(
            name=name,
            statistic=statistic,
            elements=[metric_schemas.TopNVMElement(**e) for e in elements],
            message="Top N VMs fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_top_n_vm: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
```

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_metric_operations.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add safir_monitoring/api/v1/metric_operations.py tests/test_metric_operations.py
git commit -m "feat: add Top-N Host and Top-N VM endpoints"
```

---

### Task 4: Top-N VM Testleri

**Files:**
- Modify: `tests/test_metric_operations.py`

- [ ] **Step 1: Top-N VM testlerini ekle**

`tests/test_metric_operations.py` dosyasinin sonuna ekle:

```python


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
```

- [ ] **Step 2: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_metric_operations.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_metric_operations.py
git commit -m "test: add Top-N VM formatting tests with admin/tenant hostname visibility"
```

---

### Task 5: WoW Change Endpoint

**Files:**
- Modify: `safir_monitoring/api/v1/metric_operations.py`
- Modify: `tests/test_metric_operations.py`

- [ ] **Step 1: Failing test yaz**

`tests/test_metric_operations.py` dosyasinin sonuna ekle:

```python


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
```

- [ ] **Step 2: Testin fail ettigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_metric_operations.py::TestWoWChangeCalculation -v`
Expected: FAIL — `ImportError: cannot import name '_compute_wow_change'`

- [ ] **Step 3: WoW change fonksiyonunu ve endpoint'ini implement et**

`safir_monitoring/api/v1/metric_operations.py` dosyasinin sonuna ekle:

```python


def _series_key(labels: dict) -> str:
    """Seri eslesirme icin label'lardan tekil anahtar uretir."""
    filtered = {k: v for k, v in sorted(labels.items()) if k not in {"__name__", "prometheus", "prometheus_replica"}}
    return str(filtered)


def _compute_wow_change(current_result: list, previous_result: list, statistic: str, is_admin: bool) -> list:
    """Iki haftanin Thanos sonuclarindan WoW degisim hesaplar."""
    if not current_result:
        return []

    func = _STAT_FUNCS.get(statistic, _STAT_FUNCS["avg"])

    # Onceki haftayi key'e gore indexle
    prev_map = {}
    for series in previous_result:
        key = _series_key(series.get("metric", {}))
        values = [float(v[1]) for v in series.get("values", [])]
        prev_map[key] = func(values) if values else 0

    elements = []
    for series in current_result:
        labels = series.get("metric", {})
        key = _series_key(labels)
        values = [float(v[1]) for v in series.get("values", [])]
        current_val = func(values) if values else 0
        previous_val = prev_map.get(key, 0)

        change = round(current_val - previous_val, 2)
        change_pct = round((change / previous_val) * 100, 2) if previous_val != 0 else None

        dims = _filter_dimensions(labels, is_admin)

        elements.append({
            "dimensions": dims,
            "current_week_value": round(current_val, 2),
            "previous_week_value": round(previous_val, 2),
            "change": change,
            "change_percent": change_pct,
        })

    return elements


@router.get(
    "/metrics/forecasts/wow-change",
    description="Get week-over-week change for a metric",
    responses={
        200: {"model": metric_schemas.WoWChangeResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.WoWChangeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_wow_change(
    request: Request,
    name: str = Query(..., description="Metric name"),
    dimensions: Optional[str] = Query(None, description="Label filter: 'key:value,key2:value2'"),
    statistic: str = Query("avg", description="Comparison statistic: avg, max, min"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.WoWChangeResponse:
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
            policy.authorize(context, 'metric:get_wow_change', {"project_id": project_id})

        if statistic not in _STAT_FUNCS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistic: {statistic}. Valid: avg, max, min"
            )

        now = datetime.now()
        # Bu hafta: son 7 gun
        current_end = int(now.timestamp())
        current_start = int((now - timedelta(days=7)).timestamp())
        # Gecen hafta: 14 - 7 gun once
        previous_end = current_start
        previous_start = int((now - timedelta(days=14)).timestamp())

        query = _build_query(name, project_id if not is_admin else None)

        if dimensions:
            dim_filter = ",".join(
                f'{k}="{v}"' for k, v in
                (d.split(":", 1) for d in dimensions.split(",") if ":" in d)
            )
            if "{" in query:
                query = query.replace("{", "{" + dim_filter + ",", 1)
            else:
                query = f"{query}{{{dim_filter}}}"

        LOG.info(f"WoW query: {query}")

        # Paralel olarak bu hafta ve gecen haftayi sorgula
        import asyncio
        current_task = thanos.execute_range_query_with_time(
            query=query, start=current_start, end=current_end, step="1h"
        )
        previous_task = thanos.execute_range_query_with_time(
            query=query, start=previous_start, end=previous_end, step="1h"
        )
        current_result, previous_result = await asyncio.gather(current_task, previous_task)

        elements = _compute_wow_change(current_result, previous_result, statistic, is_admin)

        return metric_schemas.WoWChangeResponse(
            name=name,
            statistic=statistic,
            elements=[metric_schemas.WoWChangeElement(**e) for e in elements],
            message="Week-over-week change calculated successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_wow_change: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
```

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/test_metric_operations.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add safir_monitoring/api/v1/metric_operations.py tests/test_metric_operations.py
git commit -m "feat: add WoW change endpoint with parallel week queries"
```

---

### Task 6: Route Registration

**Files:**
- Modify: `safir_monitoring/api/v1/__init__.py`

- [ ] **Step 1: Router'i kaydet**

`safir_monitoring/api/v1/__init__.py` dosyasina ekle:

Import (diger import'larin altina):
```python
from safir_monitoring.api.v1 import metric_operations
```

Router registration (son satira):
```python
api_router.include_router(metric_operations.router, tags=["metric-operations"])
```

- [ ] **Step 2: Route'lari dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "from safir_monitoring.api.v1 import api_router; routes=[r.path for r in api_router.routes if hasattr(r,'path')]; [print(r) for r in sorted(routes) if 'top-n' in r or 'wow' in r]"`
Expected:
```
/metrics/forecasts/wow-change
/metrics/statistics/top-n-host
/metrics/statistics/top-n-vm
```

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/api/v1/__init__.py
git commit -m "feat: register metric operations routes (top-n, wow-change)"
```

---

### Task 7: Son Dogrulama

- [ ] **Step 1: Tum testleri calistir**

Run: `cd /Users/bilgem/safir_monitoring && python3 -m pytest tests/ -v`
Expected: Tum testler PASS

- [ ] **Step 2: Import chain dogrulamasi**

Run: `cd /Users/bilgem/safir_monitoring && python3 -c "
from safir_monitoring.schemas.metrics import TopNHostResponse, TopNVMResponse, WoWChangeResponse
from safir_monitoring.api.v1 import api_router
from safir_monitoring.common.policies.metric import list_rules
print(f'Policy rules: {len(list(list_rules()))}')
routes = [r.path for r in api_router.routes if hasattr(r, 'path')]
print(f'Total routes: {len(routes)}')
new_routes = [r for r in routes if 'top-n' in r or 'wow' in r]
print(f'New Faz 2 routes: {new_routes}')
"`

Expected:
```
Policy rules: 11
Total routes: 27
New Faz 2 routes: ['/metrics/statistics/top-n-host', '/metrics/statistics/top-n-vm', '/metrics/forecasts/wow-change']
```

---

## Ozet

| Task | Dosyalar | Aciklama |
|------|----------|----------|
| 1 | schemas/metrics.py | Top-N ve WoW Pydantic schemalari |
| 2 | policies/metric.py | Policy kurallari (3 yeni) |
| 3 | metric_operations.py, test_metric_operations.py | Top-N Host + Top-N VM endpoint'leri |
| 4 | test_metric_operations.py | Top-N VM testleri (admin/tenant hostname) |
| 5 | metric_operations.py, test_metric_operations.py | WoW Change endpoint |
| 6 | __init__.py | Route registration |
| 7 | — | Son dogrulama |
