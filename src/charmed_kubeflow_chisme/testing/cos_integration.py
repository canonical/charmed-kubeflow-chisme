# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for testing COS integration with charms."""
import logging
from pathlib import Path
from typing import Any, Dict, Set

import yaml
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit

log = logging.getLogger(__name__)

GRAFANA_AGENT_APP = "grafana-agent-k8s"
METRICS_ENDPOINT_RELATION = "metrics-endpoint"
GRAFANA_DASHBOARD_RELATION = "grafana-dashboard"
ALER_RULES_DIRECTORY = Path("./src/prometheus_alert_rules")


async def deploy_and_assert_grafana_agent(
    model: Model,
    app: str,
    channel: str = "latest/stable",
    dashboard: bool = True,
    metrics: bool = True,
) -> None:
    """Deploy grafana-agent-k8 and add relate it with app.

    Helper function to deploy and relate grafana-agent-k8s with provided app.

    Args:
        model: libjuju model object
        app: name of application with which the Grafana agent should be related
        channel: grafana-agent-k8s channel name, latest/stable as default
        dashboard: relate <app>:grafana-dashboard grafana-agent-k8s:grafana-dashboards-consumer
        metrics: relate <app>:metrics-endpoint grafana-agent-k8s:metrics-endpoint
    """
    assert app in model.applications, f"application {app} was not found"

    log.info("deploying %s from %s channel", GRAFANA_AGENT_APP, channel)
    await model.deploy(GRAFANA_AGENT_APP, channel=channel)

    if dashboard is True:
        log.info(
            "juju relate %s:%s %s:grafana-dashboards-consumer",
            app,
            GRAFANA_DASHBOARD_RELATION,
            GRAFANA_AGENT_APP,
        )
        await model.add_relation(
            f"{app}:{GRAFANA_DASHBOARD_RELATION}",
            f"{GRAFANA_AGENT_APP}:grafana-dashboards-consumer",
        )

    if metrics is True:
        log.info(
            "juju relate %s:%s %s:metrics-endpoint",
            app,
            METRICS_ENDPOINT_RELATION,
            GRAFANA_AGENT_APP,
        )
        await model.add_relation(
            f"{app}:{METRICS_ENDPOINT_RELATION}", f"{GRAFANA_AGENT_APP}:metrics-endpoint"
        )

    await model.wait_for_idle(apps=[GRAFANA_AGENT_APP], status="blocked", timeout=5 * 60)


async def _check_metrics_endpoint(app: Application, metrics_endpoint: str) -> None:
    """Check metrics endpoint accessibility.

    Checking accessibility of metrics endpoint from grafana-agent-k8s. If metrics endpoint is
    defined as `*:5000/metrics` it will be changed to `<app-name>.<namespace>.svc:5000/metrics`.
    """
    if metrics_endpoint.startswith("*"):
        url = f"http://{app.name}.{app.model.name}.svc{metrics_endpoint[1:]}"
    else:
        url = f"http://{metrics_endpoint}"

    cmd = f"curl -m 5 -sS {url}"
    grafana_agent_app = app.model.applications[GRAFANA_AGENT_APP]
    log.info("testing metrics endpoint with cmd: `%s`", cmd)
    for unit in grafana_agent_app.units:
        await _run_on_unit(unit, cmd)


async def _get_app_relation_data(app: Application, endpoint_name: str) -> Dict[str, Any]:
    """Get relations from endpoint name."""
    assert len(app.units) > 0, f"application {app.name} has no units"
    unit = app.units[0]  # Note(rgildein) use first unit, since we are getting application data
    relations = [
        relation
        for relation in app.relations
        if any(endpoint.name == endpoint_name for endpoint in relation.endpoints)
    ]
    log.info("found relations %s for %s:%s", relations, app.name, endpoint_name)

    assert len(relations) == 1, f"{endpoint_name} is missing or there are too many of them"
    relation = relations[0]

    cmd = f"relation-get --format=yaml -r {relation.entity_id} --app - {app.name}"
    result = await _run_on_unit(unit, cmd)

    return yaml.safe_load(result.results["stdout"])


def _get_alert_rules(data: str) -> Set[str]:
    """Get all alert rules from string, e.g. file content or relation data.

    Example of relations data of metrics-endpoint would be:

    ```Python
    'alert_rules': '{"groups": [{rules": [{"alert": "my-alert", ...
    ```

    Example of rule file with single alert rule:

    ```yaml
    alert: my-alert
    expr: up < 1
    for: 5m
    ...
    ```

    Example of rule file with multiple alert rules:

    ```yaml
    groups:
    - name: my-group
      rules:
      - alert: my-alert
    ...
    ```
    """
    alert_rules = yaml.safe_load(data)
    if "groups" in alert_rules:
        return {rule["alert"] for group in alert_rules["groups"] for rule in group["rules"]}

    return {alert_rules["alert"]}


def _get_metrics_endpoint(data: str) -> Set[str]:
    """Get set of metrics endpoints from string.

    This function is excpection data defined as string.

    ```json
    [
      {
        "metrics_path": "/metrics",
        "static_configs": [
          {
            "targets": [
              "*:5000",
              "*:8000"
            ]
          }
        ]
      }
    ]
    ```
    """
    metrics_endpoints = set()
    scrape_jobs = yaml.safe_load(data)
    for job in scrape_jobs:
        path = job["metrics_path"]
        metrics_endpoints |= {
            f"{target}{path}" for config in job["static_configs"] for target in config["targets"]
        }

    return metrics_endpoints


async def _run_on_unit(unit: Unit, cmd: str) -> Action:
    """Run command on unit."""
    log.info("running cmd `%s` on unit %s", cmd, unit.name)
    result = await unit.run(cmd, block=True)  # Note(rgildein): Using block to wait for results

    assert (
        result.results["return-code"] == 0
    ), f"cmd `{cmd}` failed with error `{result.results.get('stderr')}`"
    return result


# def get_charm_alert_rules() -> Set[str]:
#     """Get all alert rules.

#     TODO: files with .rules can have multiple rules
#     """
#     alert_rules = set()
#     for file_type in ["*.rule", "*.rules"]:
#         for file in ALER_RULES_DIRECTORY.glob(file_type):
#             alert_rules |= _get_alert_rules(file.read_text())

#     return alert_rules


async def assert_alert_rules(app: Application, alert_rules: Set[str]) -> None:
    """Assert function comparing alert rules from relation data and provided aler rules.

    This function compare alert rules defined in METRICS_ENDPOINT_RELATION relation data bag and
    provided aler rules. e.g. {"my-alert1", "my-alert2"}
    """
    relation_data = await _get_app_relation_data(app, METRICS_ENDPOINT_RELATION)
    assert "alert_rules" in relation_data, "relation is missing alert_rules"

    relation_alert_rules = _get_alert_rules(relation_data["alert_rules"])

    assert relation_alert_rules == alert_rules


async def assert_metrics_endpoint(app: Application, metrics_endpoints: Set[str]) -> None:
    """Assert function to check defined metrics endpoints in relation data.

    This function compare metrics endpoints defined in METRICS_ENDPOINT_RELATION relation data bag
    and provided metrics endpoint. e.g. {"*:5000/metrics", "*:8000/metrics"}
    This function will also check the accessibility of such endpoint.
    """
    relation_data = await _get_app_relation_data(app, METRICS_ENDPOINT_RELATION)
    assert "scrape_jobs" in relation_data, "relation is missing scrape_jobs"

    relation_metrics_endpoints = _get_metrics_endpoint(relation_data["scrape_jobs"])

    assert relation_metrics_endpoints == metrics_endpoints
    for metrics_endpoint in relation_metrics_endpoints:
        await _check_metrics_endpoint(app, metrics_endpoint)
