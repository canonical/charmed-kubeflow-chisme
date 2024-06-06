# Chisme testing abstraction

# COS integration

## `deploy_and_assert_grafana_agent`

Helper function to deploy [grafana-agent-k8s](https://charmhub.io/grafana-agent-k8s) to the test model and add cos relations to the charm being tested. This function also checks if the grafana-agent-k8s has reached the desired state, which is blocked with a message composed of two of the following phrases "send-remote-write: off", "grafana-cloud-config: off" or "grafana-dashboards-provider: off".

Relation can be enabled/disabled by flags:
- metrics=True, to enable `<app>:metrics-endpoint grafana-agent-k8s:metrics-endpoint` relation
- dashboard=True, to enable `<app>:grafana-dashboard grafana-agent-k8s:grafana-dashboards-consumer` relation
- logging=True, to enable `<app>:logging grafana-agent-k8s:logging-provider` relation

Example usage:
```python
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    my_charm = await ops_test.build_charm(".")
    await ops_test.model.deploy(my_charm)
    await ops_test.model.wait_for_idle()

    await deploy_and_assert_grafana_agent(
        ops_test.model, "my-charm", metrics=True, dashboard=True, logging=True
        )
```

## `assert_alert_rules`

Helper function to test alert rules are defined in relation data bag.

Example usage:
```python
async def test_alert_rules(ops_test):
    """Test alert_rules are defined in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    await assert_alert_rules(app, {"MyAler1", "MyAler2"})
```

This tool also provides helper function `get_alert_rules` to collect all alert rules from charm source code, by default from './src/prometheus_alert_rules' path.

Example usage:
```python
async def test_alert_rules(ops_test):
    """Test check charm alert rules and rules defined in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    alert_rules = get_alert_rules()
    await assert_alert_rules(app, alert_rules)
```

## `assert_metrics_endpoint`

Helper function to test metrics endpoints are defined in relation data bag and to verify that endpoint is accessible from grafana-agent-k8s pod.

Example usage:
```python
async def test_metrics_enpoint(ops_test):
    """Test metrics_endpoints are defined in relation data bag and their accessibility.

    This function gets all the metrics_endpoints from the relation data bag, checks if
    they are available from the grafana-agent-k8s charm and finally compares them with the
    ones provided to the function.
    """
    app = ops_test.model.applications["my-charm"]
    await assert_metrics_endpoint(app, metrics_port=5000, metrics_path="/metrics")
    await assert_metrics_endpoint(app, metrics_port=8000, metrics_path="/metrics")
```

## `assert_logging`

Helper function to test logging is defined in relation data bag. As the 'endpoint' key is defined in the grafana-agent-k8s data bag, this function requires the grafana-agent-k8s application instead of tested charm.

Example usage:
```python
async def test_logging(ops_test):
    """Test logging is defined in relation data bag."""
    app = ops_test.model.applications[GRAFANA_AGENT_APP]
    await assert_logging(app)
```
