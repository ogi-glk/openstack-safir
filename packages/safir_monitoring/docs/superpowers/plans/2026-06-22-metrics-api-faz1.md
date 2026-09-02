# Metrics API Faz 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** safir_monitoring servisine measurements, statistics, metric names, dimension names/values, hosts ve VMs endpoint'lerini eklemek.

**Architecture:** Mevcut FastAPI + Thanos yapisi korunur. Yeni endpoint'ler metric.py'ye ve yeni metric_discovery.py dosyasina eklenir. Thanos metadata API'leri (/api/v1/labels, /api/v1/label/values, /api/v1/series) icin yeni helper fonksiyonlari thanos.py'ye eklenir.

**Tech Stack:** FastAPI, aiohttp (Thanos client), Pydantic (schemas), oslo.policy (authorization)

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `safir_monitoring/common/thanos.py` | Modify | Thanos metadata API helpers ekle |
| `safir_monitoring/schemas/metrics.py` | Modify | Yeni response/request schemalari ekle |
| `safir_monitoring/api/v1/metric.py` | Modify | measurements ve statistics endpoint'leri ekle |
| `safir_monitoring/api/v1/metric_discovery.py` | Create | names, dimensions, hosts, VMs endpoint'leri |
| `safir_monitoring/common/policies/metric.py` | Modify | Yeni policy kurallari ekle |
| `safir_monitoring/api/v1/__init__.py` | Modify | Yeni router'i kaydet |
| `tests/conftest.py` | Create | Test altyapisi |
| `tests/test_thanos_helpers.py` | Create | Thanos helper testleri |
| `tests/test_metric_endpoints.py` | Create | Measurements/statistics testleri |
| `tests/test_metric_discovery.py` | Create | Discovery endpoint testleri |

---

### Task 1: Test Altyapisi

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`

- [ ] **Step 1: pytest.ini olustur**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 2: tests/__init__.py olustur**

Bos dosya:
```python
```

- [ ] **Step 3: conftest.py olustur**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def mock_thanos_range_query():
    """Thanos execute_range_query_with_time mock'u"""
    with patch("safir_monitoring.common.thanos.execute_range_query_with_time", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_thanos_instant_query():
    """Thanos execute_instant_query mock'u"""
    with patch("safir_monitoring.common.thanos.execute_instant_query", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_thanos_labels_query():
    """Thanos get_label_names mock'u"""
    with patch("safir_monitoring.common.thanos.get_label_names", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_thanos_label_values_query():
    """Thanos get_label_values mock'u"""
    with patch("safir_monitoring.common.thanos.get_label_values", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_thanos_series_query():
    """Thanos get_series mock'u"""
    with patch("safir_monitoring.common.thanos.get_series", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_policy_authorize():
    """Policy authorize mock'u"""
    with patch("safir_monitoring.common.policy.authorize") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_policy_authorize_admin():
    """Admin policy mock'u - admin_or_owner gecen, get_admin gecen"""
    with patch("safir_monitoring.common.policy.authorize") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_policy_authorize_tenant():
    """Tenant policy mock'u - admin_or_owner gecen, get_admin reddeden"""
    from safir_monitoring.common.policy import PolicyNotAuthorized
    def side_effect(context, action, target):
        if action == 'metric:get_admin':
            raise PolicyNotAuthorized(action=action)
        return True
    with patch("safir_monitoring.common.policy.authorize", side_effect=side_effect) as mock:
        yield mock


@pytest.fixture
def mock_context():
    """Request context mock'u"""
    with patch("safir_monitoring.common.utils.req_context_from_scope", new_callable=AsyncMock) as mock:
        ctx = MagicMock()
        ctx.project_id = "test-project-123"
        ctx.to_dict.return_value = {"project_id": "test-project-123", "roles": ["member"]}
        mock.return_value = ctx
        yield mock
```

- [ ] **Step 4: pytest ve bagimliliklari kur**

Run: `pip install pytest pytest-asyncio httpx`

- [ ] **Step 5: Testlerin calistigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/ -v --co`
Expected: "no tests ran" (henuz test yok ama hata da yok)

- [ ] **Step 6: Commit**

```bash
git add tests/ pytest.ini
git commit -m "test: add test infrastructure with pytest and conftest fixtures"
```

---

### Task 2: Thanos Metadata Helper Fonksiyonlari

**Files:**
- Create: `tests/test_thanos_helpers.py`
- Modify: `safir_monitoring/common/thanos.py` (satir 252'den sonra ekle)

- [ ] **Step 1: Failing test yaz**

`tests/test_thanos_helpers.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp


@pytest.mark.asyncio
class TestGetLabelNames:
    async def test_returns_label_names_for_metric(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "data": ["__name__", "hostname", "instance", "job"]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_label_names
            result = await get_label_names(metric_name="cpu_usage_active")

        assert result == ["__name__", "hostname", "instance", "job"]

    async def test_returns_empty_list_on_no_data(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "data": []
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_label_names
            result = await get_label_names(metric_name="nonexistent")

        assert result == []


@pytest.mark.asyncio
class TestGetLabelValues:
    async def test_returns_values_for_label(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "data": ["host1", "host2", "host3"]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_label_values
            result = await get_label_values(label_name="hostname")

        assert result == ["host1", "host2", "host3"]


@pytest.mark.asyncio
class TestGetSeries:
    async def test_returns_series_list(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "success",
            "data": [
                {"__name__": "node_uname_info", "nodename": "host1", "instance": "10.0.0.1:9100"},
                {"__name__": "node_uname_info", "nodename": "host2", "instance": "10.0.0.2:9100"},
            ]
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            from safir_monitoring.common.thanos import get_series
            result = await get_series(match='node_uname_info')

        assert len(result) == 2
        assert result[0]["nodename"] == "host1"
```

- [ ] **Step 2: Testin fail ettigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_thanos_helpers.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_label_names'`

- [ ] **Step 3: Thanos helper fonksiyonlarini implement et**

`safir_monitoring/common/thanos.py` dosyasinin sonuna (satir 252'den sonra) ekle:

```python


async def get_label_names(metric_name: str = None) -> List[str]:
    """Thanos /api/v1/labels endpoint'inden label isimlerini getirir."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/labels"
            params = {}
            if metric_name:
                params["match[]"] = metric_name

            LOG.debug(f"Fetching label names: metric_name={metric_name}")

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos labels query unsuccessful: {data}")

                return data.get("data", [])

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos labels query: {str(e)}")
            raise Exception(f"Failed to fetch label names: {str(e)}")
        except Exception as e:
            LOG.error(f"Error fetching label names: {str(e)}", exc_info=True)
            raise


async def get_label_values(label_name: str, metric_name: str = None) -> List[str]:
    """Thanos /api/v1/label/<name>/values endpoint'inden label degerlerini getirir."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/label/{label_name}/values"
            params = {}
            if metric_name:
                params["match[]"] = metric_name

            LOG.debug(f"Fetching label values: label={label_name}, metric={metric_name}")

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos label values query unsuccessful: {data}")

                return data.get("data", [])

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos label values query: {str(e)}")
            raise Exception(f"Failed to fetch label values: {str(e)}")
        except Exception as e:
            LOG.error(f"Error fetching label values: {str(e)}", exc_info=True)
            raise


async def get_series(match: str) -> List[Dict[str, Any]]:
    """Thanos /api/v1/series endpoint'inden eslesen serileri getirir."""
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{CONF.thanos.querier_endpoint}/api/v1/series"
            params = {"match[]": match}

            LOG.debug(f"Fetching series: match={match}")

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise Exception(f"Thanos returned status {response.status}: {body}")

                data = await response.json()
                if data.get("status") != "success":
                    raise Exception(f"Thanos series query unsuccessful: {data}")

                return data.get("data", [])

        except aiohttp.ClientError as e:
            LOG.error(f"HTTP error during Thanos series query: {str(e)}")
            raise Exception(f"Failed to fetch series: {str(e)}")
        except Exception as e:
            LOG.error(f"Error fetching series: {str(e)}", exc_info=True)
            raise
```

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_thanos_helpers.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add safir_monitoring/common/thanos.py tests/test_thanos_helpers.py
git commit -m "feat: add Thanos metadata API helpers (labels, label values, series)"
```

---

### Task 3: Yeni Pydantic Schemalari

**Files:**
- Modify: `safir_monitoring/schemas/metrics.py` (satir 60'tan sonra ekle)

- [ ] **Step 1: Schemalari ekle**

`safir_monitoring/schemas/metrics.py` dosyasinin sonuna ekle:

```python


# ============================================================================
# MEASUREMENTS SCHEMAS
# ============================================================================

class MeasurementSeries(BaseModel):
    """Tek bir olcum serisi"""
    name: str = Field(..., description="Metric name")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Metric dimensions/labels")
    measurements: List[List] = Field(..., description="[[timestamp, value], ...]")


class MeasurementsResponse(BaseModel):
    """Measurements endpoint response"""
    data: List[MeasurementSeries] = Field(..., description="Measurement series list")
    message: str = Field("Measurements fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# STATISTICS SCHEMAS
# ============================================================================

class StatisticsSeries(BaseModel):
    """Tek bir istatistik serisi"""
    name: str = Field(..., description="Metric name")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Metric dimensions/labels")
    columns: List[str] = Field(..., description="Column names (e.g., ['timestamp', 'avg', 'min', 'max', 'count', 'sum'])")
    statistics: List[List] = Field(..., description="Statistics data rows")


class StatisticsResponse(BaseModel):
    """Statistics endpoint response"""
    data: List[StatisticsSeries] = Field(..., description="Statistics series list")
    message: str = Field("Statistics fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# METRIC NAMES SCHEMA
# ============================================================================

class MetricNamesResponse(BaseModel):
    """Metric names endpoint response"""
    metric_names: List[str] = Field(..., description="Available metric names")
    type: Optional[str] = Field(None, description="Metric type filter (user/system)")
    message: str = Field("Metric names fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# DIMENSION SCHEMAS
# ============================================================================

class DimensionNamesResponse(BaseModel):
    """Dimension names endpoint response"""
    dimension_names: List[str] = Field(..., description="Label/dimension key names")
    message: str = Field("Dimension names fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


class DimensionValuesResponse(BaseModel):
    """Dimension values endpoint response"""
    dimension_name: str = Field(..., description="Label/dimension key")
    dimension_values: List[str] = Field(..., description="Values for the dimension")
    message: str = Field("Dimension values fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


# ============================================================================
# HOST / VM SCHEMAS
# ============================================================================

class HostElement(BaseModel):
    """Tek bir host bilgisi"""
    name: str = Field(..., description="Host name")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="Host labels")


class HostListResponse(BaseModel):
    """Host list endpoint response"""
    elements: List[HostElement] = Field(..., description="Host list")
    message: str = Field("Hosts fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")


class VMElement(BaseModel):
    """Tek bir VM bilgisi"""
    name: str = Field(..., description="VM name")
    instance_id: str = Field(..., description="OpenStack instance ID")
    project_id: str = Field(default="", description="Owner project ID")
    dimensions: Dict[str, str] = Field(default_factory=dict, description="VM labels")


class VMListResponse(BaseModel):
    """VM list endpoint response"""
    elements: List[VMElement] = Field(..., description="VM list")
    message: str = Field("VMs fetched successfully")
    code: int = Field(200)
    title: str = Field("OK")
```

- [ ] **Step 2: Schemalarin import edilebildigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -c "from safir_monitoring.schemas.metrics import MeasurementsResponse, StatisticsResponse, MetricNamesResponse, DimensionNamesResponse, DimensionValuesResponse, HostListResponse, VMListResponse; print('All schemas imported OK')"`
Expected: "All schemas imported OK"

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/schemas/metrics.py
git commit -m "feat: add Pydantic schemas for measurements, statistics, dimensions, hosts/VMs"
```

---

### Task 4: Policy Kurallari

**Files:**
- Modify: `safir_monitoring/common/policies/metric.py` (satir 33'ten sonra ekle)

- [ ] **Step 1: Yeni policy kurallarini ekle**

`safir_monitoring/common/policies/metric.py` dosyasinda `metric_policies` listesine ekle (satir 33, `]` kapanmadan once):

```python
    policy.DocumentedRuleDefault(
        name='metric:get_measurements',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get metric measurements (owner or admin)',
        operations=[{'path': '/metrics/measurements',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_statistics',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get metric statistics (owner or admin)',
        operations=[{'path': '/metrics/statistics',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_names',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='List metric names',
        operations=[{'path': '/metrics/names',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_dimensions',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Get dimension names and values',
        operations=[{'path': '/metrics/dimensions/names',
                    'method': 'GET'},
                   {'path': '/metrics/dimensions/values',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_hosts',
        check_str=base.ROLE_ADMIN,
        description='List hosts (admin only)',
        operations=[{'path': '/metrics/hosts',
                    'method': 'GET'}],
    ),
    policy.DocumentedRuleDefault(
        name='metric:get_vms',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='List VMs (owner or admin)',
        operations=[{'path': '/metrics/vms',
                    'method': 'GET'}],
    ),
```

- [ ] **Step 2: Policy'nin yuklendigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -c "from safir_monitoring.common.policies.metric import list_rules; rules = list(list_rules()); print(f'{len(rules)} rules loaded'); [print(f'  - {r.name}') for r in rules]"`
Expected: 8 rules (2 mevcut + 6 yeni)

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/common/policies/metric.py
git commit -m "feat: add policy rules for new metric endpoints"
```

---

### Task 5: Measurements Endpoint

**Files:**
- Create: `tests/test_metric_endpoints.py`
- Modify: `safir_monitoring/api/v1/metric.py` (satir 204'ten sonra ekle)

- [ ] **Step 1: Failing test yaz**

`tests/test_metric_endpoints.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_thanos_result(metric_name, labels, values):
    """Thanos query_range sonucu olusturur"""
    metric_labels = {"__name__": metric_name}
    metric_labels.update(labels)
    return {"metric": metric_labels, "values": values}


@pytest.mark.asyncio
class TestMeasurementsEndpoint:
    async def test_measurements_builds_correct_response(self):
        """measurements endpoint'i Thanos sonucunu dogru formata donusturur"""
        from safir_monitoring.api.v1.metric import _format_measurements

        thanos_result = [
            _make_thanos_result(
                "cpu_usage_active",
                {"hostname": "host1"},
                [[1719014400, "65.3"], [1719014700, "67.1"]]
            )
        ]

        result = _format_measurements("cpu_usage_active", thanos_result)

        assert len(result) == 1
        assert result[0]["name"] == "cpu_usage_active"
        assert result[0]["dimensions"] == {"hostname": "host1"}
        assert result[0]["measurements"] == [[1719014400, "65.3"], [1719014700, "67.1"]]

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

        result = _format_measurements("cpu_usage_active", thanos_result)

        assert "__name__" not in result[0]["dimensions"]
        assert result[0]["dimensions"] == {"hostname": "host1", "job": "node"}

    async def test_measurements_empty_result(self):
        """Bos Thanos sonucu bos liste doner"""
        from safir_monitoring.api.v1.metric import _format_measurements

        result = _format_measurements("cpu_usage_active", [])
        assert result == []
```

- [ ] **Step 2: Testin fail ettigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_metric_endpoints.py -v`
Expected: FAIL — `ImportError: cannot import name '_format_measurements'`

- [ ] **Step 3: Measurements endpoint'ini implement et**

`safir_monitoring/api/v1/metric.py` dosyasinda satir 204'ten sonra (list_metrics fonksiyonundan sonra) ekle:

```python


# ============================================================================
# INTERNAL LABELS (Thanos response'tan cikarilacak)
# ============================================================================

_INTERNAL_LABELS = {"__name__", "prometheus", "prometheus_replica"}


def _format_measurements(metric_name: str, thanos_result: list) -> list:
    """Thanos query_range sonucunu measurements formatina donusturur."""
    series_list = []
    for series in thanos_result:
        labels = series.get("metric", {})
        dimensions = {k: v for k, v in labels.items() if k not in _INTERNAL_LABELS}
        series_list.append({
            "name": metric_name,
            "dimensions": dimensions,
            "measurements": series.get("values", []),
        })
    return series_list


@router.get(
    "/metrics/measurements",
    description="Query time series measurements from Thanos (policy: admin or owner)",
    responses={
        200: {"model": metric_schemas.MeasurementsResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.MeasurementsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_measurements(
    request: Request,
    name: str = Query(..., description="Metric name (e.g., 'cpu_usage_active')"),
    dimensions: Optional[str] = Query(
        None,
        description="Label filter, format: 'key:value,key2:value2'"
    ),
    start_time: Optional[str] = Query(
        None,
        description="Start time in ISO format. Default: 1 hour ago"
    ),
    end_time: Optional[str] = Query(
        None,
        description="End time in ISO format. Default: now"
    ),
    step: Optional[str] = Query("5m", description="Query resolution step. Default: 5m"),
    merge_metrics: Optional[bool] = Query(False, description="Combine multiple series into one"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.MeasurementsResponse:
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
            policy.authorize(context, 'metric:get_measurements', {"project_id": project_id})

        now = datetime.utcnow()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

        # PromQL query olustur
        query = _build_query(name, project_id if not is_admin else None)

        # Dimension filtresi ekle
        if dimensions:
            dim_filter = ",".join(
                f'{k}="{v}"' for k, v in
                (d.split(":", 1) for d in dimensions.split(",") if ":" in d)
            )
            if "{" in query:
                query = query.replace("{", "{" + dim_filter + ",", 1)
            else:
                query = f"{query}{{{dim_filter}}}"

        if merge_metrics:
            query = f"sum({query})"

        LOG.info(f"Measurements query: {query}")

        thanos_result = await thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step=step
        )

        series = _format_measurements(name, thanos_result)

        return metric_schemas.MeasurementsResponse(
            data=[metric_schemas.MeasurementSeries(**s) for s in series],
            message="Measurements fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_measurements: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
```

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_metric_endpoints.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add safir_monitoring/api/v1/metric.py tests/test_metric_endpoints.py
git commit -m "feat: add GET /metrics/measurements endpoint"
```

---

### Task 6: Statistics Endpoint

**Files:**
- Modify: `tests/test_metric_endpoints.py`
- Modify: `safir_monitoring/api/v1/metric.py`

- [ ] **Step 1: Failing test yaz**

`tests/test_metric_endpoints.py` dosyasinin sonuna ekle:

```python


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

        # 6 data point, 300s arayla = 1800s toplam
        values = [
            [1719014400, "10.0"],  # bucket 1: 0-599
            [1719014700, "20.0"],  # bucket 1
            [1719015000, "30.0"],  # bucket 2: 600-1199
            [1719015300, "40.0"],  # bucket 2
            [1719015600, "50.0"],  # bucket 3: 1200-1799
            [1719015900, "60.0"],  # bucket 3
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
```

- [ ] **Step 2: Testin fail ettigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_metric_endpoints.py::TestStatisticsFormatting -v`
Expected: FAIL — `ImportError: cannot import name '_compute_statistics'`

- [ ] **Step 3: Statistics endpoint'ini implement et**

`safir_monitoring/api/v1/metric.py` dosyasinda measurements endpoint'inden sonra ekle:

```python


def _compute_statistics(values: list, statistics: list, period: int = None) -> list:
    """Thanos values listesinden istatistikleri hesaplar.

    Args:
        values: [[timestamp, value_str], ...] formatinda zaman serisi
        statistics: Hesaplanacak istatistikler listesi (avg, min, max, count, sum)
        period: Aggregation periyodu (saniye). None ise tum veri tek bucket.

    Returns:
        [[timestamp, stat1, stat2, ...], ...] formatinda sonuc
    """
    if not values:
        return []

    # Float'a cevir
    parsed = [(v[0], float(v[1])) for v in values]

    # Period'a gore bucket'la
    if period and period > 0:
        start_ts = parsed[0][0]
        buckets = {}
        for ts, val in parsed:
            bucket_key = start_ts + ((ts - start_ts) // period) * period
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(val)
        bucket_list = sorted(buckets.items())
    else:
        bucket_list = [(parsed[0][0], [v for _, v in parsed])]

    # Her bucket icin istatistikleri hesapla
    result = []
    stat_funcs = {
        "avg": lambda vals: sum(vals) / len(vals),
        "min": lambda vals: min(vals),
        "max": lambda vals: max(vals),
        "count": lambda vals: len(vals),
        "sum": lambda vals: sum(vals),
    }

    for ts, vals in bucket_list:
        row = [ts]
        for stat in statistics:
            func = stat_funcs.get(stat)
            if func:
                row.append(func(vals))
        result.append(row)

    return result


VALID_STATISTICS = {"avg", "min", "max", "count", "sum"}


@router.get(
    "/metrics/statistics",
    description="Get aggregated statistics for a metric (policy: admin or owner)",
    responses={
        200: {"model": metric_schemas.StatisticsResponse},
        400: {"model": metric_schemas.BadRequestMessage},
        401: {"model": metric_schemas.UnauthorizedMessage},
        403: {"model": metric_schemas.ForbiddenMessage},
        500: {"model": metric_schemas.InternalServerErrorMessage},
    },
    response_model=metric_schemas.StatisticsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_statistics(
    request: Request,
    name: str = Query(..., description="Metric name"),
    statistics: str = Query(..., description="Comma-separated: avg,min,max,count,sum"),
    dimensions: Optional[str] = Query(None, description="Label filter: 'key:value,key2:value2'"),
    start_time: Optional[str] = Query(None, description="Start time ISO format. Default: 1 hour ago"),
    end_time: Optional[str] = Query(None, description="End time ISO format. Default: now"),
    period: Optional[int] = Query(None, description="Aggregation period in seconds"),
    project_id: Optional[str] = Query(None, description="Project ID (required for non-admin)"),
    X_Auth_Token: str = Header(default=None),
) -> metric_schemas.StatisticsResponse:
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
            policy.authorize(context, 'metric:get_statistics', {"project_id": project_id})

        # statistics parametresini dogrula
        stat_list = [s.strip() for s in statistics.split(",")]
        invalid = set(stat_list) - VALID_STATISTICS
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid statistics: {invalid}. Valid: {VALID_STATISTICS}"
            )

        now = datetime.utcnow()
        end_unix = parse_time_to_unix(end_time) if end_time else int(now.timestamp())
        start_unix = parse_time_to_unix(start_time) if start_time else int((now - timedelta(hours=1)).timestamp())

        if start_unix >= end_unix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be before end_time"
            )

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

        # Thanos'tan ham veriyi cek (yuksek resolution)
        resolution_step = f"{period}s" if period else "60s"

        LOG.info(f"Statistics query: {query}, stats={stat_list}, period={period}")

        thanos_result = await thanos.execute_range_query_with_time(
            query=query, start=start_unix, end=end_unix, step=resolution_step
        )

        # Her seri icin istatistikleri hesapla
        columns = ["timestamp"] + stat_list
        series_list = []
        for series in thanos_result:
            labels = series.get("metric", {})
            dims = {k: v for k, v in labels.items() if k not in _INTERNAL_LABELS}
            values = series.get("values", [])
            stats = _compute_statistics(values, stat_list, period=period)
            series_list.append(
                metric_schemas.StatisticsSeries(
                    name=name,
                    dimensions=dims,
                    columns=columns,
                    statistics=stats,
                )
            )

        return metric_schemas.StatisticsResponse(
            data=series_list,
            message="Statistics fetched successfully",
            code=200,
            title="OK"
        )

    except HTTPException:
        raise
    except Exception as e:
        LOG.error(f"Error in get_statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
```

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_metric_endpoints.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add safir_monitoring/api/v1/metric.py tests/test_metric_endpoints.py
git commit -m "feat: add GET /metrics/statistics endpoint"
```

---

### Task 7: Discovery Endpoint'leri (Names, Dimensions, Hosts, VMs)

**Files:**
- Create: `safir_monitoring/api/v1/metric_discovery.py`
- Create: `tests/test_metric_discovery.py`
- Modify: `safir_monitoring/api/v1/__init__.py` (satir 17'den sonra ekle)

- [ ] **Step 1: Failing test yaz**

`tests/test_metric_discovery.py`:
```python
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
                "instance": "10.0.0.1:9177",
            },
        ]

        result = _format_vms(series)

        assert len(result) == 1
        assert result[0]["name"] == "web-server-1"
        assert result[0]["instance_id"] == "abc-123"
        assert result[0]["project_id"] == "proj-1"

    async def test_deduplicates_vms(self):
        from safir_monitoring.api.v1.metric_discovery import _format_vms

        series = [
            {"instance_name": "vm1", "instance_id": "id-1", "project_id": "p1"},
            {"instance_name": "vm1", "instance_id": "id-1", "project_id": "p1"},
        ]

        result = _format_vms(series)
        assert len(result) == 1
```

- [ ] **Step 2: Testin fail ettigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_metric_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'safir_monitoring.api.v1.metric_discovery'`

- [ ] **Step 3: metric_discovery.py olustur**

`safir_monitoring/api/v1/metric_discovery.py`:
```python
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
    for s in series:
        instance_id = s.get("instance_id", "")
        if instance_id in seen:
            continue
        seen.add(instance_id)
        name = s.get("instance_name", s.get("domain", "unknown"))
        project_id = s.get("project_id", "")
        dimensions = {k: v for k, v in s.items()
                      if k not in _INTERNAL_LABELS | {"instance_name", "instance_id", "project_id", "domain"}}
        vms.append({
            "name": name,
            "instance_id": instance_id,
            "project_id": project_id,
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

        names = await thanos.get_label_values("__name__")

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
```

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/test_metric_discovery.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add safir_monitoring/api/v1/metric_discovery.py tests/test_metric_discovery.py
git commit -m "feat: add metric discovery endpoints (names, dimensions, hosts, VMs)"
```

---

### Task 8: Route Registration

**Files:**
- Modify: `safir_monitoring/api/v1/__init__.py`

- [ ] **Step 1: Yeni router'i kaydet**

`safir_monitoring/api/v1/__init__.py` dosyasini su sekilde guncelle:

Satir 8'den sonra ekle:
```python
from safir_monitoring.api.v1 import metric_discovery
```

Satir 17'den sonra (son include_router'dan sonra) ekle:
```python
api_router.include_router(metric_discovery.router, tags=["metric-discovery"])
```

Dosyanin son hali:
```python
from fastapi import APIRouter

from safir_monitoring.api.v1 import alert_webhook
from safir_monitoring.api.v1 import notification
from safir_monitoring.api.v1 import alarm_rule
from safir_monitoring.api.v1 import quotas
from safir_monitoring.api.v1 import metric
from safir_monitoring.api.v1 import alarm_history
from safir_monitoring.api.v1 import metric_discovery

api_router = APIRouter()

api_router.include_router(notification.router, tags=["notification"])
api_router.include_router(alarm_rule.router, tags=["alarm-rule"])
api_router.include_router(alert_webhook.router, tags=["alerts"])
api_router.include_router(quotas.router, tags=["quotas"])
api_router.include_router(metric.router, tags=["metric"])
api_router.include_router(alarm_history.router, tags=["alarm-history"])
api_router.include_router(metric_discovery.router, tags=["metric-discovery"])
```

- [ ] **Step 2: Import'larin calistigini dogrula**

Run: `cd /Users/bilgem/safir_monitoring && python -c "from safir_monitoring.api.v1 import api_router; routes = [r.path for r in api_router.routes]; print('\n'.join(sorted(routes)))"`
Expected: Tum endpoint yollari listelenir (mevcut + yeni 7 endpoint)

- [ ] **Step 3: Commit**

```bash
git add safir_monitoring/api/v1/__init__.py
git commit -m "feat: register metric discovery routes"
```

---

### Task 9: Tum Testlerin Calistirilmasi ve Son Dogrulama

**Files:** Hicbir dosya degisikligi yok — sadece dogrulama

- [ ] **Step 1: Tum testleri calistir**

Run: `cd /Users/bilgem/safir_monitoring && python -m pytest tests/ -v`
Expected: Tum testler PASS

- [ ] **Step 2: Import chain dogrulamasi**

Run: `cd /Users/bilgem/safir_monitoring && python -c "
from safir_monitoring.api.v1 import api_router
from safir_monitoring.schemas.metrics import (
    MeasurementsResponse, StatisticsResponse, MetricNamesResponse,
    DimensionNamesResponse, DimensionValuesResponse, HostListResponse, VMListResponse
)
from safir_monitoring.common.thanos import get_label_names, get_label_values, get_series
from safir_monitoring.common.policies.metric import list_rules
print('All imports OK')
rules = list(list_rules())
print(f'Policy rules: {len(rules)}')
routes = [r.path for r in api_router.routes]
print(f'Routes: {len(routes)}')
for r in sorted(routes):
    print(f'  {r}')
"`

Expected:
```
All imports OK
Policy rules: 8
Routes: <mevcut + 7 yeni>
  /metrics
  /metrics/dimensions/names
  /metrics/dimensions/values
  /metrics/hosts
  /metrics/list
  /metrics/measurements
  /metrics/names
  /metrics/statistics
  /metrics/vms
  ...
```

- [ ] **Step 3: Son commit (gerekirse)**

Eger onceki adimda duzeltme yapildiysa:
```bash
git add -A
git commit -m "fix: resolve any remaining issues from integration testing"
```

---

## Ozet

| Task | Dosyalar | Aciklama |
|------|----------|----------|
| 1 | tests/conftest.py, pytest.ini | Test altyapisi |
| 2 | thanos.py, test_thanos_helpers.py | Thanos metadata helpers |
| 3 | schemas/metrics.py | Yeni Pydantic schemalari |
| 4 | policies/metric.py | Policy kurallari |
| 5 | metric.py, test_metric_endpoints.py | Measurements endpoint |
| 6 | metric.py, test_metric_endpoints.py | Statistics endpoint |
| 7 | metric_discovery.py, test_metric_discovery.py | Names, dimensions, hosts, VMs |
| 8 | __init__.py | Route registration |
| 9 | — | Son dogrulama |
