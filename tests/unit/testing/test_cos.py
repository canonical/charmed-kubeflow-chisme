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
from tenacity import stop_after_attempt

from charmed_kubeflow_chisme.testing.cos_integration import (
    _check_url,
    _get_alert_rules,
    _get_app_from_relation,
    _get_app_relation_data,
    _get_charm_name,
    _get_dashboard_template,
    _get_metrics_endpoint,
    _get_relation,
    _get_targets_from_grafana_agent,
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

GRAFANA_AGENT_METRICS_TARGETS = """
{
  "status": "success",
  "data": [
    {
      "instance": "ad3e396dc08b0f42a6e4b57e90bed6e2",
      "target_group": "integrations/agent",
      "endpoint": "http://127.0.0.1:12345/integrations/agent/metrics",
      "state": "up",
      "labels": {
        "agent_hostname": "grafana-agent-k8s-0",
        "instance": "kubeflow_c8c8_grafana-agent-k8s_grafana-agent-k8s/0",
        "job": "juju_kubeflow_c8c8_grafana-agent-k8s_self-monitoring",
        "juju_application": "grafana-agent-k8s",
        "juju_charm": "grafana-agent-k8s",
        "juju_model": "kubeflow",
        "juju_model_uuid": "c8c8",
        "juju_unit": "grafana-agent-k8s/0"
      },
      "discovered_labels": {
        "__address__": "127.0.0.1:12345",
        "__metrics_path__": "/integrations/agent/metrics",
        "__scheme__": "http",
        "__scrape_interval__": "1m",
        "__scrape_timeout__": "10s",
        "agent_hostname": "grafana-agent-k8s-0",
        "job": "integrations/agent"
      },
      "last_scrape": "2024-06-28T12:04:32.864964737Z",
      "scrape_duration_ms": 3,
      "scrape_error": ""
    },
    {
      "instance": "ad3e396dc08b0f42a6e4b57e90bed6e2",
      "target_group": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
      "endpoint": "http://10.1.23.239:5558/metrics",
      "state": "up",
      "labels": {
        "instance": "kubeflow_c8c8_dex-auth_dex-auth/0",
        "job": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
        "juju_application": "dex-auth",
        "juju_charm": "dex-auth",
        "juju_model": "kubeflow",
        "juju_model_uuid": "c8c8",
        "juju_unit": "dex-auth/0"
      },
      "discovered_labels": {
        "__address__": "10.1.23.239:5558",
        "__metrics_path__": "/metrics",
        "__scheme__": "http",
        "__scrape_interval__": "1m",
        "__scrape_timeout__": "10s",
        "job": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
        "juju_application": "dex-auth",
        "juju_charm": "dex-auth",
        "juju_model": "kubeflow",
        "juju_model_uuid": "c8c8",
        "juju_unit": "dex-auth/0"
      },
      "last_scrape": "2024-06-28T12:04:58.60872202Z",
      "scrape_duration_ms": 1,
      "scrape_error": ""
    },
    {
      "instance": "ad3e396dc08b0f42a6e4b57e90bed6e2",
      "target_group": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
      "endpoint": "http://10.1.23.239:8080/metrics",
      "state": "up",
      "labels": {
        "instance": "kubeflow_c8c8_dex-auth_dex-auth/0",
        "job": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
        "juju_application": "dex-auth",
        "juju_charm": "dex-auth",
        "juju_model": "kubeflow",
        "juju_model_uuid": "c8c8",
        "juju_unit": "dex-auth/0"
      },
      "discovered_labels": {
        "__address__": "10.1.23.239:8080",
        "__metrics_path__": "/metrics",
        "__scheme__": "http",
        "__scrape_interval__": "1m",
        "__scrape_timeout__": "10s",
        "job": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
        "juju_application": "dex-auth",
        "juju_charm": "dex-auth",
        "juju_model": "kubeflow",
        "juju_model_uuid": "c8c8",
        "juju_unit": "dex-auth/0"
      },
      "last_scrape": "2024-06-28T12:04:58.60872202Z",
      "scrape_duration_ms": 1,
      "scrape_error": ""
    }
  ]
}
"""


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
        ({"wait_timeout": 100}, []),
    ],
)
async def test_deploy_and_assert_grafana_agent(kwargs, exp_awaits):
    """Test deploy grafana-agent-k8s along test app."""
    app = Mock(spec_set=Application)()
    app.name = "my-app"

    grafana_agent_app = Mock(spec_set=Application)()
    grafana_agent_app.name = "grafana-agent-k8s"
    grafana_agent_unit = Mock(spec_set=Unit)()
    grafana_agent_app.units = [grafana_agent_unit]

    model = AsyncMock(spec_set=Model)
    model.applications = {app.name: app, grafana_agent_app.name: grafana_agent_app}

    await deploy_and_assert_grafana_agent(model, app.name, **kwargs)
    expected_wait_timeout = kwargs.get("wait_timeout", 300)

    model.deploy.assert_awaited_once_with("grafana-agent-k8s", channel="1/stable")
    model.integrate.assert_has_awaits(exp_awaits)
    model.wait_for_idle.assert_awaited_once_with(
        apps=["grafana-agent-k8s"], status="blocked", timeout=expected_wait_timeout, idle_period=60
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


def test_get_app_from_relation_provides():
    """Test get application from provide side of relation."""
    relation = Mock(spec_set=Relation)()
    app = _get_app_from_relation(relation, "provides")
    assert app == relation.provides.application


def test_get_app_from_relation_requires():
    """Test get application from provide side of relation."""
    relation = Mock(spec_set=Relation)()
    app = _get_app_from_relation(relation, "requires")
    assert app == relation.requires.application


def test_get_app_from_relation_fail():
    """Test get application from unknown side of relation and fail."""
    relation = Mock(spec_set=Relation)()
    with pytest.raises(ValueError, match="unknown is invalid side of relation."):
        _get_app_from_relation(relation, "unknown")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_relation")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_from_relation")
async def test_get_app_relation_data_no_units(mock_get_app_from_relation, mock_get_relation):
    """Test getting application data from relation data bag without units."""
    app = Mock(spec_set=Application)()
    app.name = "my-app"
    app.units = []
    mock_get_app_from_relation.return_value = app

    with pytest.raises(AssertionError, match="application my-app has no units"):
        await _get_app_relation_data(app, "metrics-endpoint", "provides")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_relation")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_from_relation")
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
@patch("charmed_kubeflow_chisme.testing.cos_integration.yaml")
async def test_get_app_relation_data(
    mock_yaml, mock_run_on_unit, mock_get_app_from_relation, mock_get_relation
):
    """Test getting application data from relation data bag."""
    relation = Mock(spec_set=Relation)()
    relation.entity_id = relation_id = 7
    mock_get_relation.return_value = relation
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    app.name = "my-app"
    app.units = [unit]
    mock_get_app_from_relation.return_value = app
    mock_run_on_unit.return_value = result = Mock(spec_set=Action)()
    result.results = {"stdout": "test"}

    data = await _get_app_relation_data(app, "metrics-endpoint", "provides")

    mock_get_relation.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_app_from_relation.assert_called_once_with(relation, "provides")
    mock_run_on_unit.assert_awaited_once_with(
        unit, f"relation-get --format=yaml -r {relation_id} --app - {app.name}"
    )
    mock_yaml.safe_load.assert_called_once_with("test")
    assert data == mock_yaml.safe_load.return_value


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_relation")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_from_relation")
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
@patch("charmed_kubeflow_chisme.testing.cos_integration.yaml")
async def test_get_unit_relation_data(
    mock_yaml, mock_run_on_unit, mock_get_app_from_relation, mock_get_relation
):
    """Test getting unit data from relation data bag."""
    relation = Mock(spec_set=Relation)()
    relation.entity_id = relation_id = 7
    mock_get_relation.return_value = relation
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    unit.name = "my-app/0"
    app.name = "my-app"
    app.units = [unit]
    mock_get_app_from_relation.return_value = app
    mock_run_on_unit.return_value = result = Mock(spec_set=Action)()
    result.results = {"stdout": "test"}

    data = await _get_unit_relation_data(app, "metrics-endpoint", "provides")

    mock_get_relation.assert_awaited_once_with(app, "metrics-endpoint")
    mock_get_app_from_relation.assert_called_once_with(relation, "provides")
    mock_run_on_unit.assert_awaited_once_with(
        unit, f"relation-get --format=yaml -r {relation_id} - {unit.name}"
    )
    mock_yaml.safe_load.assert_called_once_with("test")
    assert data == {unit.name: mock_yaml.safe_load.return_value}


@pytest.mark.parametrize(
    "url, port, path, exp_result",
    [
        ("http://1.2.3.4:9090/metrics", 9090, "/metrics", True),
        ("http://1.2.3.4:9090/metrics", 9091, "/metrics", False),
        ("http://1.2.3.4:9090/metrics", 9090, "/my-metrics", False),
        (
            "*:9090/metrics",
            9090,
            "/metrics",
            False,
        ),  # urlparse could not parse with // or https://
        ("//*:9090/metrics", 9090, "/metrics", True),
        ("//*:9090/metrics", 9091, "/metrics", False),
        ("//*:9090/metrics", 9090, "/my-metrics", False),
        ("//blackbox-exporter-k8s-0.test.svc.cluster.local:9115/metrics", 9115, "/metrics", True),
    ],
)
def test_check_url(url, port, path, exp_result):
    """Test helpet function to check port and path in url."""
    assert _check_url(url, port, path) is exp_result


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
@pytest.mark.parametrize("port, path", [(5558, "/metrics"), (8080, "/metrics")])
async def test_get_targets_from_grafana_agent(mock_run_on_unit, port, path):
    """Test get defined targets from grafana-agent-k8s."""
    exp_cmd = "curl -m 5 -sS localhost:12345/agent/api/v1/metrics/targets"
    mock_run_on_unit.return_value = Mock(spec_set=Action)()
    mock_run_on_unit.return_value.results = {"stdout": GRAFANA_AGENT_METRICS_TARGETS}

    grafana_agent_k8s_app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    grafana_agent_k8s_app.units = [unit]

    app = Mock(spec_set=Application)()
    app.name = "dex-auth"
    app.model.applications = {"grafana-agent-k8s": grafana_agent_k8s_app, "dex-auth": app}

    target_data = await _get_targets_from_grafana_agent(app, port, path)

    assert target_data != {}
    assert target_data["state"] == "up"
    assert target_data["endpoint"] == f"http://10.1.23.239:{port}{path}"
    assert target_data["labels"]["juju_application"] == "dex-auth"
    assert target_data["labels"]["juju_model"] == "kubeflow"
    mock_run_on_unit.assert_awaited_once_with(unit, exp_cmd)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
async def test_get_targets_from_grafana_agent_no_target(mock_run_on_unit):
    """Test get defined targets from grafana-agent-k8s returns no data."""
    exp_cmd = "curl -m 5 -sS localhost:12345/agent/api/v1/metrics/targets"
    mock_run_on_unit.return_value = Mock(spec_set=Action)()
    mock_run_on_unit.return_value.results = {"stdout": GRAFANA_AGENT_METRICS_TARGETS}

    grafana_agent_k8s_app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    grafana_agent_k8s_app.units = [unit]

    app = Mock(spec_set=Application)()
    app.name = "dex-auth"
    app.model.applications = {"grafana-agent-k8s": grafana_agent_k8s_app, "dex-auth": app}

    # using a port not defined in the example above
    target_data = await _get_targets_from_grafana_agent(app, 9090, "/metrics")

    assert target_data == {}
    mock_run_on_unit.assert_awaited_once_with(unit, exp_cmd)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._run_on_unit")
async def test_get_charm_name(mock_run_on_unit):
    """Test get charm name from metadata."""
    app = Mock(spec_set=Application)()
    unit = Mock(spec_set=Unit)()
    app.units = [unit]

    action = Mock(spec_set=Action)()
    action.results = {"stdout": "name: my-charm"}
    mock_run_on_unit.return_value = action

    charm_name = await _get_charm_name(app)
    assert charm_name == "my-charm"


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


@pytest.mark.parametrize(
    "data, exp_templates",
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
def test__get_dashboard_template(data, exp_templates):
    """Test helper function to get Grafana dashboards from string."""
    assert _get_dashboard_template(data) == exp_templates


@pytest.mark.parametrize(
    "data, exp_metrics_endpoint",
    [
        (
            '[{"metrics_path": "/metrics", "static_configs": [{"targets": ["*:5000","*:8000"]}]}]',
            {"*:5000/metrics", "*:8000/metrics"},
        ),
        (
            '[{"metrics_path": "/metrics", "static_configs": [{"targets": ["10.152.183.18:8889", '
            '"*:9090"]}]}]',
            {"10.152.183.18:8889/metrics", "*:9090/metrics"},
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

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint", side="provides")
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

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint", side="provides")
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

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint", side="provides")
    mock_get_alert_rules.assert_called_once_with("...")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_metrics_endpoint")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_targets_from_grafana_agent")
async def test_assert_metrics_endpoint_no_data(
    mock_get_targets_from_grafana_agent, mock_get_metrics_endpoint, mock_get_app_relation_data
):
    """Test assert function for metrics endpoint with empty data bag."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {}
    # Wait once instead of 10 times to speed up tests
    # as per https://github.com/jd/tenacity/issues/106
    assert_metrics_endpoint.retry.stop = stop_after_attempt(1)

    with pytest.raises(AssertionError, match="metrics-endpoint relation is missing 'scrape_jobs'"):
        await assert_metrics_endpoint(app, metrics_port=8000, metrics_path="/metrics")

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint", side="provides")
    mock_get_metrics_endpoint.assert_not_called()
    mock_get_targets_from_grafana_agent.assert_not_awaited()


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_metrics_endpoint")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_targets_from_grafana_agent")
async def test_assert_metrics_endpoint(
    mock_get_targets_from_grafana_agent, mock_get_metrics_endpoint, mock_get_app_relation_data
):
    """Test assert function for metrics endpoint."""
    app = Mock(spec_set=Application)()
    app.name = "dex-auth"
    app.model.name = "kubeflow"
    mock_get_app_relation_data.return_value = {"scrape_jobs": "..."}
    mock_get_metrics_endpoint.return_value = {"*:5558/metrics"}
    mock_get_targets_from_grafana_agent.return_value = {
        "instance": "ad3e396dc08b0f42a6e4b57e90bed6e2",
        "target_group": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
        "endpoint": "http://10.1.23.239:5558/metrics",
        "state": "up",
        "labels": {
            "instance": "kubeflow_c8c8_dex-auth_dex-auth/0",
            "job": "juju_kubeflow_34eea852_dex-auth_prometheus_scrape-0",
            "juju_application": "dex-auth",
            "juju_charm": "dex-auth",
            "juju_model": "kubeflow",
            "juju_model_uuid": "c8c8",
            "juju_unit": "dex-auth/0",
        },
    }
    # Wait once instead of 10 times to speed up tests
    # as per https://github.com/jd/tenacity/issues/106
    assert_metrics_endpoint.retry.stop = stop_after_attempt(1)

    await assert_metrics_endpoint(app, metrics_port=5558, metrics_path="/metrics")

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint", side="provides")
    mock_get_metrics_endpoint.assert_called_once_with("...")
    mock_get_targets_from_grafana_agent.assert_awaited_once_with(app, 5558, "/metrics")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_metrics_endpoint")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_targets_from_grafana_agent")
async def test_assert_metrics_endpoint_fail(
    mock_get_targets_from_grafana_agent, mock_get_metrics_endpoint, mock_get_app_relation_data
):
    """Test assert function for metrics endpoint failing."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"scrape_jobs": "..."}
    mock_get_metrics_endpoint.return_value = {"*:5000/metrics"}

    with pytest.raises(AssertionError):
        await assert_metrics_endpoint(app, metrics_port=8000, metrics_path="/metrics")

    mock_get_app_relation_data.assert_awaited_once_with(app, "metrics-endpoint", side="provides")
    mock_get_metrics_endpoint.assert_called_once_with("...")
    mock_get_targets_from_grafana_agent.assert_not_awaited()


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_unit_relation_data")
async def test_assert_logging(mock_get_unit_relation_data):
    """Test assert function for logging endpoint."""
    app = Mock(spec_set=Application)()
    mock_get_unit_relation_data.return_value = {"my-app/0": {"endpoint": "..."}}

    await assert_logging(app)

    mock_get_unit_relation_data.assert_awaited_once_with(app, "logging", side="provides")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_unit_relation_data")
async def test_assert_logging_fail(mock_get_unit_relation_data):
    """Test assert function for logging endpoint."""
    app = Mock(spec_set=Application)()
    mock_get_unit_relation_data.return_value = {"my-app/0": {}}

    with pytest.raises(AssertionError):
        await assert_logging(app)

    mock_get_unit_relation_data.assert_awaited_once_with(app, "logging", side="provides")


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_dashboard_template")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_charm_name")
async def test_assert_grafana_dashboards_no_data(
    mock_get_charm_name, mock_get_dashboard_template, mock_get_app_relation_data
):
    """Test assert function for Grafana dashboards with empty data bag."""
    exp_error = "grafana-dashboard relation data is missing 'dashboards'"
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {}

    with pytest.raises(AssertionError, match=exp_error):
        await assert_grafana_dashboards(app, {})

    mock_get_app_relation_data.assert_awaited_once_with(app, "grafana-dashboard", side="provides")
    mock_get_dashboard_template.assert_not_called()
    mock_get_charm_name.assert_not_awaited()


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_dashboard_template")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_charm_name")
async def test_assert_grafana_dashboard(
    mock_get_charm_name, mock_get_dashboard_template, mock_get_app_relation_data
):
    """Test assert function for Grafana dashboards."""
    app = Mock(spec_set=Application)()
    mock_get_charm_name.return_value = app.charm_name = "my-charm"
    mock_get_app_relation_data.return_value = {"dashboards": "..."}
    mock_get_dashboard_template.return_value = {
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

    mock_get_app_relation_data.assert_awaited_once_with(app, "grafana-dashboard", side="provides")
    mock_get_dashboard_template.assert_called_once_with("...")
    mock_get_charm_name.assert_awaited_once_with(app)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_app_relation_data")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_dashboard_template")
@patch("charmed_kubeflow_chisme.testing.cos_integration._get_charm_name")
async def test_assert_grafana_dashboards_fail(
    mock_get_charm_name, mock_get_dashboard_template, mock_get_app_relation_data
):
    """Test assert function for Grafana dashboards failing."""
    app = Mock(spec_set=Application)()
    mock_get_app_relation_data.return_value = {"dashboards": "..."}
    mock_get_dashboard_template.return_value = {"my-dashboard-1": {}, "my-dashboard-2": {}}

    with pytest.raises(AssertionError):
        await assert_grafana_dashboards(app, {"different-dashboards"})

    mock_get_app_relation_data.assert_awaited_once_with(app, "grafana-dashboard", side="provides")
    mock_get_dashboard_template.assert_called_once_with("...")
    mock_get_charm_name.assert_not_awaited()


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
