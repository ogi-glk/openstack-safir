import pytest
from unittest.mock import AsyncMock, patch, MagicMock


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
