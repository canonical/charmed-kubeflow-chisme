# Chisme testing abstraction

# COS integration

## `deploy_and_assert_grafana_agent`

Helper function to deploy [grafana-agent-k8s](https://charmhub.io/grafana-agent-k8s) to test the model and add a relation to the charm being tested.
Relation can be disabledled by flags:
- dashboard=False, to disable `<app>:grafana-dashboard grafana-agent-k8s:grafana-dashboards-consumer` relation
- metrics=False, to disable `<app>:metrics-endpoint grafana-agent-k8s:metrics-endpoint` relation

Example usage:
```python
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    my_charm = await ops_test.build_charm(".")
    my_charm_name = ops_test._charm_name(my_charm)
    await ops_test.model.deploy(my_charm)
    await ops_test.model.wait_for_idle()

    await deploy_and_assert_grafana_agent(ops_test.model, my_charm_name)
```

## `assert_alert_rules`

Helper function to test alert rules define in relation data bag.

Example usage:
```python
async def test_alert_rules(ops_test):
    """Test alert_rules defione in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    await assert_alert_rules(app, {"MyAler1", "MyAler2"})
```

## `assert_metrics_endpoint`

Helper function to test metrics endpoints define in relation data bag.

Example usage:
```python
async def test_metrics_enpoint(ops_test):
    """Test metrics_endpoint defione in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    await assert_metrics_endpoint(app, {"*:5000/metrics", "*:8000/metrics"})
```
