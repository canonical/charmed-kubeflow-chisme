# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest

from charmed_kubeflow_chisme.testing import (
    assert_alert_rules,
    assert_metrics_endpoints,
    deploy_and_assert_grafana_agent,
)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    """Test deployment of grafana-agent-k8s and relate it with charm."""
    await ops_test.model.deploy("mlflow", channel="latest/stable", trust=True)
    await ops_test.model.wait_for_idle()

    await deploy_and_assert_grafana_agent(ops_test.model, "mlflow-server")


async def test_alert_rules(ops_test):
    """Test alert_rules are defined in relation data bag."""
    app = ops_test.model.applications["mlflow-server"]
    await assert_alert_rules(
        app, {"MLFlowServerUnitIsUnavailable", "MLFlowRequestDurationTooLong"}
    )


async def test_metrics_endpoints(ops_test):
    """Test metrics_endpoints are defined in relation data bag."""
    app = ops_test.model.applications["mlflow-server"]
    await assert_metrics_endpoints(app, {"*:5000/metrics", "*:8000/metrics"})
