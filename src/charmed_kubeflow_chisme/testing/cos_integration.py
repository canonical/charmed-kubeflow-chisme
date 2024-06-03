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
from juju.relation import Relation
from juju.unit import Unit

log = logging.getLogger(__name__)

GRAFANA_AGENT_APP = "grafana-agent-k8s"
GRAFANA_AGENT_METRICS_ENDPOINT = "metrics-endpoint"
GRAFANA_AGENT_GRAFANA_DASHBOARD = "grafana-dashboards-consumer"
GRAFANA_AGENT_LOGGING_PROVIDER = "logging-provider"
# Note(rgildein): The status message comes from the helper function `_update_status` in
# grafana-agent-k8s, which is used to set the status based on the health of the relation.
# https://github.com/canonical/grafana-agent-operator/blob/
# 71b092445d47252f07a5e6c70ee730235eba18ba/src/grafana_agent.py#L471-L483
GRAFANA_AGENT_MESSAGE = {
    "send-remote-write: off",
    "grafana-cloud-config: off",
    "grafana-dashboards-provider: off",
}

APP_METRICS_ENDPOINT = "metrics-endpoint"
APP_GRAFANA_DASHBOARD = "grafana-dashboard"
APP_LOGGING = "logging"

ALERT_RULES_DIRECTORY = Path("./src/prometheus_alert_rules")


async def deploy_and_assert_grafana_agent(
    model: Model,
    app: str,
    channel: str = "latest/stable",
    metrics: bool = True,
    logging: bool = True,
    dashboard: bool = False,
) -> None:
    """Deploy grafana-agent-k8s and add relate it with app.

    Helper function to deploy and relate grafana-agent-k8s with provided app.

    Args:
        model (juju.model.Model): Juju model object.
        app (str): Name of application with which the Grafana agent should be related.
        channel (str): Channel name for grafana-agent-k8s. Defaults to latest/stable.
        metrics (bool): Boolean that defines if the <app>:metrics-endpoint
            grafana-agent-k8s:metrics-endpoint relation is created. Defaults to True.
        logging (bool): Boolean that defines if the <app>:logging
            grafana-agent-k8s:logging-provider relation is created. Defaults to True.
        dashboard (bool): Boolean that defines if the <app>:grafana-dashboard
            grafana-agent-k8s:grafana-dashboards-consumer relation is created. Defaults to False.
    """
    assert app in model.applications, f"application {app} was not found in model {model.name}"

    log.info("deploying %s from %s channel", GRAFANA_AGENT_APP, channel)
    await model.deploy(GRAFANA_AGENT_APP, channel=channel)

    if dashboard is True:
        log.info(
            "Adding relation: %s:%s and %s:%s",
            app,
            APP_GRAFANA_DASHBOARD,
            GRAFANA_AGENT_APP,
            GRAFANA_AGENT_GRAFANA_DASHBOARD,
        )
        await model.integrate(
            f"{app}:{APP_GRAFANA_DASHBOARD}",
            f"{GRAFANA_AGENT_APP}:{GRAFANA_AGENT_GRAFANA_DASHBOARD}",
        )

    if metrics is True:
        log.info(
            "Adding relation: %s:%s and %s:%s",
            app,
            APP_METRICS_ENDPOINT,
            GRAFANA_AGENT_APP,
            GRAFANA_AGENT_METRICS_ENDPOINT,
        )
        await model.integrate(
            f"{app}:{APP_METRICS_ENDPOINT}",
            f"{GRAFANA_AGENT_APP}:{GRAFANA_AGENT_METRICS_ENDPOINT}",
        )

    if logging is True:
        log.info(
            "Adding relation: %s:%s and %s:%s",
            app,
            APP_LOGGING,
            GRAFANA_AGENT_APP,
            GRAFANA_AGENT_LOGGING_PROVIDER,
        )
        await model.integrate(
            f"{app}:{APP_LOGGING}",
            f"{GRAFANA_AGENT_APP}:{GRAFANA_AGENT_LOGGING_PROVIDER}",
        )

    # Note(rgildein): Since we are not deploying cos, grafana-agent-k8s will in block state with
    # missing relations.
    await model.wait_for_idle(apps=[GRAFANA_AGENT_APP], status="blocked", timeout=5 * 60)
    for unit in model.applications[GRAFANA_AGENT_APP].units:
        # create set from string like `grafana-cloud-config: off, grafana-dashboards-provider: off`
        msg = {pmsg.strip() for pmsg in unit.workload_status_message.split(",")}
        # if msg is empty or contains something else than GRAFANA_AGENT_MESSAGE it will fail
        assert (
            GRAFANA_AGENT_MESSAGE & msg
        ), f"{GRAFANA_AGENT_APP} did not reach expected state. '{msg}' != '{GRAFANA_AGENT_MESSAGE}'"


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


async def _get_relation(app: Application, endpoint_name: str) -> Relation:
    """Get relation for endpoint."""
    assert len(app.units) > 0, f"application {app.name} has no units"
    relations = [
        relation
        for relation in app.relations
        if any(endpoint.name == endpoint_name for endpoint in relation.endpoints)
    ]
    log.info("found relations %s for %s:%s", relations, app.name, endpoint_name)

    assert not (len(relations) == 0), f"{endpoint_name} is missing"
    assert not (len(relations) > 1), f"too many relations with {endpoint_name} endpoint"
    return relations[0]


async def _get_app_relation_data(app: Application, endpoint_name: str) -> Dict[str, Any]:
    """Get application relation data from endpoint name."""
    relation = await _get_relation(app, endpoint_name)
    unit = app.units[0]  # Note(rgildein) use first unit, since we are getting application data
    cmd = f"relation-get --format=yaml -r {relation.entity_id} --app - {app.name}"
    result = await _run_on_unit(unit, cmd)

    return yaml.safe_load(result.results["stdout"])


async def _get_unit_relation_data(
    app: Application, endpoint_name: str
) -> Dict[str, Dict[str, Any]]:
    """Get units relation data from endpoint name."""
    relation = await _get_relation(app, endpoint_name)
    data = {}
    for unit in app.units:
        cmd = f"relation-get --format=yaml -r {relation.entity_id} - {unit.name}"
        result = await _run_on_unit(unit, cmd)
        data[unit.name] = yaml.safe_load(result.results["stdout"])

    return data


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

    This function is expecting data defined as string.

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


def get_alert_rules(path: Path = ALERT_RULES_DIRECTORY) -> Set[str]:
    """Get all alert rules from files.

    Args:
        path (Path): Path of alert rules directory. Defaults to "./src/prometheus_alert_rules".

    Returns:
        set[str]: Set with all alert rules.
    """
    alert_rules = set()
    for file_type in ["*.rule", "*.rules"]:
        for file in path.glob(file_type):
            alert_rules |= _get_alert_rules(file.read_text())

    return alert_rules


async def assert_alert_rules(app: Application, alert_rules: Set[str]) -> None:
    """Assert function to check alert rules in relation data bag.

    This function compare alert rules defined in APP_METRICS_ENDPOINT relation data bag and
    provided alert rules. e.g. {"my-alert1", "my-alert2"}

    Args:
        app (Application): Juju Applicatition object.
        alert_rules (set[str]): Set of alert rules.
    """
    relation_data = await _get_app_relation_data(app, APP_METRICS_ENDPOINT)
    assert (
        "alert_rules" in relation_data
    ), f"{APP_METRICS_ENDPOINT} relation is missing 'alert_rules'"

    relation_alert_rules = _get_alert_rules(relation_data["alert_rules"])

    assert relation_alert_rules == alert_rules, f"{relation_alert_rules}\n!=\n{alert_rules}"


async def assert_metrics_endpoints(app: Application, metrics_endpoints: Set[str]) -> None:
    """Assert function to check defined metrics endpoints in relation data bag.

    This function compare metrics endpoints defined in APP_METRICS_ENDPOINT relation data bag
    and provided metrics endpoint. e.g. {"*:5000/metrics", "*:8000/metrics"}
    At the same time it will check the accessibility of such endpoint from grafana-agent-k8s pod.

    Args:
        app (Application): Juju Applicatition object.
        metrics_endpoints (set[str]): Set of metrics endpoints.
    """
    relation_data = await _get_app_relation_data(app, APP_METRICS_ENDPOINT)
    assert (
        "scrape_jobs" in relation_data
    ), f"{APP_METRICS_ENDPOINT} relation is missing 'scrape_jobs'"

    relation_metrics_endpoints = _get_metrics_endpoint(relation_data["scrape_jobs"])

    assert (
        relation_metrics_endpoints == metrics_endpoints
    ), f"{relation_metrics_endpoints}\n!=\n{metrics_endpoints}"
    for metrics_endpoint in relation_metrics_endpoints:
        await _check_metrics_endpoint(app, metrics_endpoint)


async def assert_logging(app: Application) -> None:
    """Assert function to check defined logging settings in relation data bag.

    This function check if endpoint is defined in logging relation data bag, the unit
    relation data bag and not application.. e.g.
    ```yaml
    related-units:
      grafana-agent-k8s/0:
        in-scope: true
        data:
          endpoint: |
            '{"url": "http://grafana-agent-k8s-0.grafana-agent-k8s-endpoints.
            my-model.svc.cluster.local:3500/loki/api/v1/push"}'
          ...
    ```

    Args:
        app (Application): Juju Applicatition object.
    """
    unit_relation_data = await _get_unit_relation_data(app, APP_LOGGING)
    for unit_name, unit_data in unit_relation_data.items():
        assert (
            "endpoint" in unit_data
        ), f"{APP_LOGGING} unit '{unit_name}' relation data are missing 'endpoint'"
