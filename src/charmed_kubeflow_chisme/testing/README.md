# Chisme testing abstraction

# Charm Spec

## CharmSpec
Dataclass used for defining dependency charms that need to be deployed during tests. This enables modifying those programmatically across all repos, according to each release's values. You can define charms like this:
```
MINIO = CharmSpec(charm="minio", channel="latest/edge", trust=True, config={"access-key": "minio", "secret-key": "minio-secret-key"})
MYSQL_K8s = CharmSpec(charm="mysql-k8s", channel="8.0/stable", trust=True, config={"profile": "testing"})
```

## `generate_context_from_charm_spec_list`
Function to generate context for rendering a yaml template from a list of CharmSpec objects. This can be used for cases where a bundle.yaml is deployed during tests (e.g. kfp bundle integration tests). For example, if Minio is a dependency charm:
```
MINIO = CharmSpec(charm="minio", channel="latest/edge", trust=True, config={"access-key": "minio", "secret-key": "minio-secret-key"})
```
and there is this entry `bundle.yaml.j2` file:
```
  minio:
    charm: {{ minio_charm }}
    channel: {{ minio_channel }}
    base: ubuntu@20.04/stable
    scale: 1
    trust: {{ minio_trust }}
```
the `generate_context_from_charm_spec_list(charms)` will generate all the necessary context, where `charms` is the list of the imported CharmSpec objects.

# COS integration

## `deploy_and_assert_grafana_agent`

Helper function to deploy [grafana-agent-k8s](https://charmhub.io/grafana-agent-k8s) to the test model and add cos relations to the charm being tested. This function also checks if the grafana-agent-k8s has reached the desired blocked state.

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

Helper function to test alert rules are defined in relation data bag. This function is using provides side of relation to get such data.

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

Helper function to test metrics endpoints are defined in relation data bag and to verify that endpoint are defined in current defined targets, via Grafana agent API [1]. This function is using provides side of relation to get such data. Note that this function is retried 10 times by default.

Example usage:
```python
async def test_metrics_enpoint(ops_test):
    """Test metrics_endpoints are defined in relation data bag and their accessibility.

    This function gets all the metrics_endpoints from the relation data bag, checks if
    they are available in current defined targets in Grafana agent.
    """
    app = ops_test.model.applications["my-charm"]
    await assert_metrics_endpoint(app, metrics_port=5000, metrics_path="/metrics")
    await assert_metrics_endpoint(app, metrics_port=8000, metrics_path="/metrics")
```

## `assert_logging`

Helper function to test logging is defined in relation data bag. As the 'endpoint' key is defined in the grafana-agent-k8s data bag, this function is using provides side of relation to get such data. This means that the related app (grafana-agent-k8s) is used to get relation unit data.

Example usage:
```python
async def test_logging(ops_test):
    """Test logging is defined in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    await assert_logging(app)
```

## `assert_grafana_dashboards`

Helper function to test dashboards are defined in relation data bag. This function is using provides side of relation to get such data.

Example usage:
```python
async def test_grafana_dashboards(ops_test):
    """Test Grafana dashboards are defined in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    await assert_grafana_dashboards(app, {"my-dashboard.json"})
```

This tool also provides helper function `get_grafana_dashboards` to collect all Grafana dashboards from charm source code, by default from './src/grafana_dashboards' path.

Example usage:
```python
async def test_grafana_dashboards(ops_test):
    """Test Grafana dashboards are defined in relation data bag."""
    app = ops_test.model.applications["my-charm"]
    dashboards = get_grafana_dashboards()
    await assert_grafana_dashboards(app, dashboards)
```

---
[1]: https://grafana.com/docs/agent/latest/static/api/#list-current-scrape-targets-of-metrics-subsystem
