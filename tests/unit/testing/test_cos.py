# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.relation import Endpoint, Relation
from juju.unit import Unit

from charmed_kubeflow_chisme.testing.cos_integration import (
    _check_metrics_endpoint,
    _get_alert_rules,
    _get_app_relation_data,
    _get_metrics_endpoint,
    _get_relation,
    _get_templates,
    _get_unit_relation_data,
    _run_on_unit,
    assert_alert_rules,
    assert_grafana_dashboards,
    assert_logging,
    assert_metrics_endpoint,
    deploy_and_assert_grafana_agent,
    get_alert_rules,
    get_grafana_dashboards,
)


@pytest.mark.asyncio
async def test_deploy_and_assert_grafana_agent_invalid_app():
    """Test deploy grafana-agent-k8s along not existing app."""
    app = "my-app"
    model = AsyncMock(spec_set=Model)
    model.applications = []

    with pytest.raises(AssertionError, match=f"application {app} was not found"):
        await deploy_and_assert_grafana_agent(model, app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs, exp_awaits",
    [
        (
            {"metrics": True, "dashboard": True, "logging": True},
            [
                call("my-app:grafana-dashboard", "grafana-agent-k8s:grafana-dashboards-consumer"),
                call("my-app:metrics-endpoint", "grafana-agent-k8s:metrics-endpoint"),
                call("my-app:logging", "grafana-agent-k8s:logging-provider"),
            ],
        ),
        (
            {"metrics": True, "dashboard": True, "logging": False},
            [
                call("my-app:grafana-dashboard", "grafana-agent-k8s:grafana-dashboards-consumer"),
                call("my-app:metrics-endpoint", "grafana-agent-k8s:metrics-endpoint"),
            ],
        ),
        (
            {"metrics": True, "dashboard": False, "logging": True},
            [
                call("my-app:metrics-endpoint", "grafana-agent-k8s:metrics-endpoint"),
                call("my-app:logging", "grafana-agent-k8s:logging-provider"),
            ],
        ),
        (
            {"metrics": True, "dashboard": False, "logging": False},
            [
                call("my-app:metrics-endpoint", "grafana-agent-k8s:metrics-endpoint"),
            ],
        ),
        ({"dashboard": False, "metrics": False, "logging": False}, []),
    ],
)
async def test_deploy_and_assert_grafana_agent(kwargs, exp_awaits):
    """Test deploy grafana-agent-k8s along test app."""
    app = Mock(spec_set=Application)()
    app.name = "my-app"

    grafana_aget_app = Mock(spec_set=Application)()
    grafana_aget_app.name = "grafana-agent-k8s"
    grafana_aget_unit = Mock(spec_set=Unit)()
    grafana_aget_app.units = [grafana_aget_unit]

    model = AsyncMock(spec_set=Model)
    model.applications = {app.name: app, grafana_aget_app.name: grafana_aget_app}

    await deploy_and_assert_grafana_agent(model, app.name, **kwargs)

    model.deploy.assert_awaited_once_with("grafana-agent-k8s", channel="latest/stable")
    model.integrate.assert_has_awaits(exp_awaits)
    model.wait_for_idle.assert_awaited_once_with(
        apps=["grafana-agent-k8s"], status="blocked", timeout=300
    )


@pytest.mark.asyncio
async def test_get_relation_no_relations():
    """Test getting not existing relation."""
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    app.name = "my-app"
    app.units = [unit]
    relation = Mock(spec_set=Relation)()
    endpoint = Mock(spec_set=Endpoint)()
    endpoint.name = "different-endpoint"
    relation.endpoints = [endpoint]
    app.relations = [relation]

    with pytest.raises(AssertionError, match="metrics-endpoint is missing"):
        await _get_relation(app, "metrics-endpoint")


@pytest.mark.asyncio
async def test_get_relation_too_many():
    """Test getting relation, when there is too many of them."""
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    app.name = "my-app"
    app.units = [unit]
    relation = Mock(spec_set=Relation)()
    endpoint = Mock(spec_set=Endpoint)()
    endpoint.name = "metrics-endpoint"
    relation.endpoints = [endpoint]
    app.relations = [relation] * 3  # three relations

    with pytest.raises(AssertionError, match="too many relations with metrics-endpoint endpoint"):
        await _get_relation(app, "metrics-endpoint")


@pytest.mark.asyncio
async def test_get_relation():
    """Test getting relation."""
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    app.name = "my-app"
    app.units = [unit]
    relation = Mock(spec_set=Relation)()
    endpoint = Mock(spec_set=Endpoint)()
    endpoint.name = "metrics-endpoint"
    relation.endpoints = [endpoint]
    app.relations = [relation]

    assert await _get_relation(app, "metrics-endpoint") == relation


@pytest.mark.asyncio
async def test_get_app_relation_data_no_units():
    """Test getting application data from relation data bag without units."""
    app = Mock(spec_set=Application)()
    app.name = "my-app"
    app.units = []

    with pytest.raises(AssertionError, match="application my-app has no units"):
        await _get_app_relation_data(app, "metrics-endpoint")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_relation")
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
@patch("charmed_kubeflow_chisme.testing.cos_integration.yaml")
async def test_get_app_relation_data(mock_yaml, mock_run_on_unit, mock_get_relation):
    """Test getting application data from relation data bag."""
    relation = Mock(spec_set=Relation)()
    relation.entity_id = relation_id = 7
    mock_get_relation.return_value = relation
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    app.name = "my-app"
    app.units = [unit]
    mock_run_on_unit.return_value = result = Mock(spec_set=Action)()
    result.results = {"stdout": "test"}

    data = await _get_app_relation_data(app, "metrics-endpoint")

    mock_run_on_unit.assert_awaited_once_with(
        unit, f"relation-get --format=yaml -r {relation_id} --app - {app.name}"
    )
    mock_yaml.safe_load.assert_called_once_with("test")
    assert data == mock_yaml.safe_load.return_value


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_relation")
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
@patch("charmed_kubeflow_chisme.testing.cos_integration.yaml")
async def test_get_unit_relation_data(mock_yaml, mock_run_on_unit, mock_get_relation):
    """Test getting unit data from relation data bag."""
    relation = Mock(spec_set=Relation)()
    relation.entity_id = relation_id = 7
    mock_get_relation.return_value = relation
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    unit.name = "my-app/0"
    app.name = "my-app"
    app.units = [unit]
    mock_run_on_unit.return_value = result = Mock(spec_set=Action)()
    result.results = {"stdout": "test"}

    data = await _get_unit_relation_data(app, "metrics-endpoint")

    mock_run_on_unit.assert_awaited_once_with(
        unit, f"relation-get --format=yaml -r {relation_id} - {unit.name}"
    )
    mock_yaml.safe_load.assert_called_once_with("test")
    assert data == {unit.name: mock_yaml.safe_load.return_value}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metrics_endpoint, exp_cmd",
    [
        ("*:5000/metrics", "curl -m 5 -sS http://my-app.my-model.svc:5000/metrics"),
        ("1.2.3.4:5000/metrics", "curl -m 5 -sS http://1.2.3.4:5000/metrics"),
    ],
)
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
async def test_check_metrics_endpoint(mock_run_on_unit, metrics_endpoint, exp_cmd):
    """Test check metrics endpoints."""
    grafana_agent_k8s_app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    grafana_agent_k8s_app.units = [unit]

    app = Mock(spec_set=Application)()
    app.name = "my-app"
    app.model = AsyncMock(spec_set=Model)
    app.model.name = "my-model"
    app.model.applications = {"grafana-agent-k8s": grafana_agent_k8s_app, "my-app": app}

    await _check_metrics_endpoint(app, metrics_endpoint)

    mock_run_on_unit.assert_awaited_once_with(unit, exp_cmd)


@pytest.mark.parametrize(
    "data, exp_alert_rules",
    [
        ('{"groups": [{"rules": [{"alert": "my-alert"}]}]}', {"my-alert"}),
        ("alert: my-alert\nexpr: up < 1\nfor: 5m", {"my-alert"}),
        (
            "groups:\n- name: my-group1\n  rules:\n  - alert: my-alert1\n"
            "- name: my-group2\n  rules:\n  - alert: my-alert2",
            {"my-alert1", "my-alert2"},
        ),
    ],
)
def test__get_alert_rules(data, exp_alert_rules):
    """Test helper function to get alert rules from string."""
    assert _get_alert_rules(data) == exp_alert_rules


"""

"""


@pytest.mark.parametrize(
    "data, exp_alert_rules",
    [
        (
            '{"templates": {"file:blackbox.json": {"charm": "blackbox-exporter-k8s", "content": "abc", "juju_topology":'
            '{"model": "test", "model_uuid": "1234", "application": "blackbox-exporter-k8s", "unit": '
            '"blackbox-exporter-k8s/0"}, "inject_dropdowns": true, "dashboard_alt_uid": "ee8f"}}, "uuid": "5f6"}',
            {
                "blackbox.json": {
                    "charm": "blackbox-exporter-k8s",
                    "juju_topology": {
                        "model": "test",
                        "model_uuid": "1234",
                        "application": "blackbox-exporter-k8s",
                        "unit": "blackbox-exporter-k8s/0",
                    },
                }
            },
        ),
        (
            '{"templates": {"file:a.json": {"charm": "a", "juju_topology": {}}, '
            '"file:b.json": {"charm": "b", "juju_topology": {}}}}',
            {
                "a.json": {"charm": "a", "juju_topology": {}},
                "b.json": {"charm": "b", "juju_topology": {}},
            },
        ),
    ],
)
def test__get_templates(data, exp_alert_rules):
    """Test helper function to get Grafana dashboards from string."""
    assert _get_templates(data) == exp_alert_rules


@pytest.mark.parametrize(
    "data, exp_metrics_endpoint",
    [
        (
            '[{"metrics_path": "/metrics", "static_configs": [{"targets": ["*:5000","*:8000"]}]}]',
            {"*:5000/metrics", "*:8000/metrics"},
        ),
    ],
)
def test_get_metrics_endpoint(data, exp_metrics_endpoint):
    """Test helper function to get metrics endpoints from string."""
    assert _get_metrics_endpoint(data) == exp_metrics_endpoint


@pytest.mark.asyncio
async def test_run_on_unit_fail():
    """Test run cmd on unit with failure."""
    unit = Mock(spec_set=Unit)()
    unit.name = "my-app/0"
    unit.run = mock_result = AsyncMock(spec_set=Unit.run)
    mock_result.return_value.results = {"return-code": 1}

    with pytest.raises(AssertionError, match="cmd `test` failed with error `None`"):
        await _run_on_unit(unit, "test")


@pytest.mark.asyncio
async def test_run_on_unit():
    """Test run cmd on unit."""
    unit = Mock(spec_set=Unit)()
    unit.name = "my-app/0"
    unit.run = AsyncMock()
    unit.run.return_value.results = {"return-code": 0}

    result = await _run_on_unit(unit, "test")

    assert result == unit.run.return_value
    unit.run.assert_awaited_once_with("test", block=True)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_alert_rules")
async def test_assert_alert_rules_no_data(mock_get_alert_rules, mock_get_app_relation_data):
    """Test assert function for alert rules with empty data bag."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {}

    with pytest.raises(AssertionError, match="metrics-endpoint relation is missing 'alert_rules'"):
        await assert_alert_rules(app, {})

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_alert_rules.assert_not_called()


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_alert_rules")
async def test_assert_alert_rules(mock_get_alert_rules, mock_get_app_relation_data):
    """Test assert function for alert rules."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"alert_rules": "..."}
    mock_get_alert_rules.return_value = exp_alert_rules = {"my-alert1", "my-alert2"}

    await assert_alert_rules(app, exp_alert_rules)

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_alert_rules.assert_called_once_with("...")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_alert_rules")
async def test_assert_alert_rules_fail(mock_get_alert_rules, mock_get_app_relation_data):
    """Test assert function for alert rules failing."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"alert_rules": "..."}
    mock_get_alert_rules.return_value = {"my-alert1", "my-alert2"}

    with pytest.raises(AssertionError):
        await assert_alert_rules(app, {"different-alert"})

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_alert_rules.assert_called_once_with("...")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_metrics_endpoint")
@patch("charmed_kubeflow_chisme.testing.cos_integration._check_metrics_endpoint")
async def test_assert_metrics_endpoint(
    mock_check_metrics_endpoint, mock_get_metrics_endpoint, mock_get_app_relation_data
):
    """Test assert function for metrics endpoint with empty data bag."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {}

    with pytest.raises(AssertionError, match="relation is missing scrape_jobs"):
        await assert_metrics_endpoint(app, metrics_port=8000, metrics_path="/metrics")

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_metrics_endpoint.assert_not_called()
    mock_check_metrics_endpoint.assert_not_awaited()


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_metrics_endpoint")
@patch("charmed_kubeflow_chisme.testing.cos_integration._check_metrics_endpoint")
async def test_assert_metrics_endpoint(
    mock_check_metrics_endpoint, mock_get_metrics_endpoint, mock_get_app_relation_data
):
    """Test assert function for metrics endpoint."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"scrape_jobs": "..."}
    mock_get_metrics_endpoint.return_value = {"*:5000/metrics"}

    await assert_metrics_endpoint(app, metrics_port=5000, metrics_path="/metrics")

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_metrics_endpoint.assert_called_once_with("...")
    mock_check_metrics_endpoint.assert_awaited_once_with(app, "*:5000/metrics")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_metrics_endpoint")
@patch("charmed_kubeflow_chisme.testing.cos_integration._check_metrics_endpoint")
async def test_assert_metrics_endpoint_fail(
    mock_check_metrics_endpoint, mock_get_metrics_endpoint, mock_get_app_relation_data
):
    """Test assert function for metrics endpoint failing."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"scrape_jobs": "..."}
    mock_get_metrics_endpoint.return_value = {"*:5000/metrics"}

    with pytest.raises(AssertionError):
        await assert_metrics_endpoint(app, metrics_port=8000, metrics_path="/metrics")

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_metrics_endpoint.assert_called_once_with("...")
    mock_check_metrics_endpoint.assert_not_awaited()


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_unit_relation_data")
async def test_assert_logging(mock_get_unit_relation_data):
    """Test assert function for logging endpoint."""
    app = Mock(spec_set=Application)()
    mock_get_unit_relation_data.return_value = {"my-app/0": {"endpoint": "..."}}

    await assert_logging(app)

    mock_get_unit_relation_data.assert_awaited_once_with(app, "logging")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_unit_relation_data")
async def test_assert_logging_fail(mock_get_unit_relation_data):
    """Test assert function for logging endpoint."""
    app = Mock(spec_set=Application)()
    mock_get_unit_relation_data.return_value = {"my-app/0": {}}

    with pytest.raises(AssertionError):
        await assert_logging(app)

    mock_get_unit_relation_data.assert_awaited_once_with(app, "logging")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_templates")
async def test_assert_grafana_dashboards_no_data(mock_get_templates, mock_get_app_relation_data):
    """Test assert function for Grafana dashboards with empty data bag."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {}

    with pytest.raises(AssertionError, match="grafana-dashboard relation is missing 'dashboards'"):
        await assert_grafana_dashboards(app, {})

    mock_get_app_relation_data.assert_awaited_once_with(app, "grafana-dashboard")
    mock_get_templates.assert_not_called()


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_templates")
async def test_assert_grafana_dashboard(mock_get_templates, mock_get_app_relation_data):
    """Test assert function for Grafana dashboards."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"dashboards": "..."}
    mock_get_templates.return_value = {
        "my-dashboard-1": {
            "charm": app.charm_name,
            "juju_topology": {"model": app.model.name, "application": app.name},
        },
        "my-dashboard-2": {
            "charm": app.charm_name,
            "juju_topology": {"model": app.model.name, "application": app.name},
        },
    }
    exp_dashboards = {"my-dashboard-1", "my-dashboard-2"}

    await assert_grafana_dashboards(app, exp_dashboards)

    mock_get_app_relation_data.assert_awaited_once_with(app, "grafana-dashboard")
    mock_get_templates.assert_called_once_with("...")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_templates")
async def test_assert_grafana_dashboards_fail(mock_get_templates, mock_get_app_relation_data):
    """Test assert function for Grafana dashboards failing."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"dashboards": "..."}
    mock_get_templates.return_value = {"my-dashboard-1": {}, "my-dashboard-2": {}}

    with pytest.raises(AssertionError):
        await assert_grafana_dashboards(app, {"different-dashboards"})

    mock_get_app_relation_data.assert_awaited_once_with(app, "grafana-dashboard")
    mock_get_templates.assert_called_once_with("...")


def test_get_alert_rules():
    """Test load alert rules from directory."""
    exp_alert_rules = {"MyAlert1", "MyAlert2"}
    path = Path(__file__).parent / "../data"

    assert get_alert_rules(path) == exp_alert_rules


def test_get_grafana_dashboards(tmp_path):
    """Test load Grafana dashboards from directory."""
    exp_alert_rules = {"my-dashboard-1.json", "my-dashboard-2.json"}
    (tmp_path / "my-dashboard-1.json.tmpl").touch()
    (tmp_path / "my-dashboard-2.json.tmpl").touch()

    assert get_grafana_dashboards(tmp_path) == exp_alert_rules
