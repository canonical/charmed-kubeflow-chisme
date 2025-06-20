# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import sh

import charmed_kubeflow_chisme.testing
from charmed_kubeflow_chisme.testing import (
    assert_alert_rules,
    assert_grafana_dashboards,
    assert_logging,
    assert_metrics_endpoint,
    deploy_and_assert_grafana_agent,
    get_alert_rules,
)

# Note(rgildein): Change app metrics endpoint, since blackbox-exporter-k8s is not using
# 'metrics-endpoint'.
charmed_kubeflow_chisme.testing.cos_integration.APP_METRICS_ENDPOINT = "self-metrics-endpoint"
TESTED_APP = "blackbox-exporter-k8s"
TESTED_APP_CHANNEL = "1/stable"


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_build_and_deploy(ops_test):
    """Test deployment of grafana-agent-k8s and relate it with charm."""
    await ops_test.model.deploy(TESTED_APP, channel=TESTED_APP_CHANNEL, trust=True)
    await ops_test.model.wait_for_idle(raise_on_blocked=True)

    await deploy_and_assert_grafana_agent(
        ops_test.model, TESTED_APP, metrics=True, dashboard=True, logging=True
    )


async def test_alert_rules(ops_test):
    """Test alert_rules are defined in relation data bag."""
    app = ops_test.model.applications[TESTED_APP]
    charm_alert_rules = fetch_alert_rules_from_downloaded_charm("blackbox-exporter-k8s")
    await assert_alert_rules(app, charm_alert_rules)


async def test_metrics_endpoints(ops_test):
    """Test metrics_endpoints are defined in relation data bag."""
    app = ops_test.model.applications["blackbox-exporter-k8s"]
    await assert_metrics_endpoint(app, 9115, "/metrics")


async def test_logging(ops_test):
    """Test logging is defined in relation data bag."""
    app = ops_test.model.applications[TESTED_APP]
    await assert_logging(app)


async def test_grafana_dashboards(ops_test):
    """Test Grafana dashboards are defined in relation data bag."""
    app = ops_test.model.applications[TESTED_APP]
    await assert_grafana_dashboards(app, {"blackbox.json"})


def fetch_alert_rules_from_downloaded_charm(charm: str):
    """Fetch alert rules from downloaded .charm file.

    Fetch alert rules dynamically to ensure tests do not break
    whenever the alert rules are updated on the charm.
    """
    temp_dir = Path("tests/tmp")
    try:
        temp_dir.mkdir()

        # Download charm under temp_dir
        try:
            # With `--channel 1/stable`, Juju CLI returns error even when the channel exists.
            sh.juju.download(
                charm,
                "--channel",
                "1/stable",
                "--base",
                "ubuntu@20.04",
                _err_to_out=True,
                _out=print,
                _cwd=temp_dir,
            )
        except sh.ErrorReturnCode as e:
            pytest.fail(f"Charm download failed: {e}")

        # Extract content into temp_dir
        charm_file_path = next(Path(temp_dir).glob("*.charm"), None)
        with ZipFile(charm_file_path) as charm_file:
            charm_file.extractall(temp_dir)
        charm_file.close()

        # Get alert rules using `get_alert_rules()`. This assumes that alert rules are stored in
        # the default `src/prometheus_alert_rules` directory.
        alert_rules_path = Path(f"{temp_dir}/src/prometheus_alert_rules")
        return get_alert_rules(alert_rules_path)

    finally:
        # Ensure cleanup even if test fails
        shutil.rmtree(temp_dir)
