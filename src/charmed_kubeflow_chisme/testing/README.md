# Chisme testing abstraction

# COS integration

## `deploy_and_assert_grafana_agent`

Helper function to deploy [grafana-agent-k8s](https://charmhub.io/grafana-agent-k8s) to the test model and add cos relations to the charm being tested. This function also checks if the grafana-agent has reached the desired state, which is blocked with the "send-remote-write: off, grafana-cloud-config: off" message.

Relation can be enable/disabled by flags:
- metrics=False, to disable `<app>:metrics-endpoint grafana-agent-k8s:metrics-endpoint` relation
- dashboard=True, to enable `<app>:grafana-dashboard grafana-agent-k8s:grafana-dashboards-consumer` relation

Example usage:
```python
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    my_charm = await ops_test.build_charm(".")
    await ops_test.model.deploy(my_charm)
    await ops_test.model.wait_for_idle()

    await deploy_and_assert_grafana_agent(ops_test.model, "my-charm", dashboard=True)
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

This tool also provides helper function `get_alert_rules` to collect all alert rules from charm source code.

Example usage:
```python
async def test_alert_rules(ops_test):
    """Test alert_rules are defined in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    alert_rules = get_alert_rules()
    await assert_alert_rules(app, alert_rules)
```

## `assert_metrics_endpoint`

Helper function to test metrics endpoints are defined in relation data bag and to verify that endpoint is accessible from grafana-agent-k8s pod.

Example usage:
```python
async def test_metrics_enpoints(ops_test):
    """Test metrics_endpoints are defined in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    await assert_metrics_endpoints(app, {"*:5000/metrics", "*:8000/metrics"})
```

## `assert_logging`

Helper function to test logging is defined in relation data bag. As the 'endpoint' key is defined in the grafana-agent-k8s data bag, this function requires the grafana-agent-k8s application instead of tested charm.

Example usage:
```python
async def test_metrics_enpoints(ops_test):
    """Test logging is defined in relation data bag."""
    app = ops_test.model.applications[GRAFANA_AGENT_APP]
    await assert_logging(app)
```
