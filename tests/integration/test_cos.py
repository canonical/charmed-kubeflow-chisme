# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest

import charmed_kubeflow_chisme.testing
from charmed_kubeflow_chisme.testing import (
    assert_alert_rules,
    assert_grafana_dashboards,
    assert_logging,
    assert_metrics_endpoint,
    deploy_and_assert_grafana_agent,
)

# Note(rgildein): Change app metrics endpoint, since blackbox-exporter-k8s is not using
# 'metrics-endpoint'.
charmed_kubeflow_chisme.testing.cos_integration.APP_METRICS_ENDPOINT = "self-metrics-endpoint"
TESTED_APP = "blackbox-exporter-k8s"
TESTED_APP_CHANNEL = "latest/stable"


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
    await assert_alert_rules(
        app,
        {
            "BlackboxJobMissing",
            "BlackboxExporterSSLCertExpiringSoon15Days",
            "BlackboxExporterSSLCertExpiringSoon30Days",
            "BlackboxExporterUnitIsUnavailable",
            "BlackboxExporterUnitIsDown",
        },
    )


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
