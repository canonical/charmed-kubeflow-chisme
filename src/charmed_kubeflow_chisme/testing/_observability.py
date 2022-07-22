import logging
import json
import requests


log = logging.getLogger(__name__)


async def test_prometheus_grafana_integration(application_name: str, ops_test):
    """Deploy prometheus, grafana and required relations, then test the metrics.

    TODO: Should grafana and prometheus be fixtures here, so they don't stay around?  Or should
          we just treat them as part of the model, and if they'll break other tests then they
          should be in a separate test file?
    """
    prometheus = "prometheus-k8s"
    grafana = "grafana-k8s"
    prometheus_scrape = "prometheus-scrape-config-k8s"
    scrape_config = {"scrape_interval": "30s"}

    # Deploy and relate prometheus
    await ops_test.model.deploy(prometheus, channel="latest/edge", trust=True)
    await ops_test.model.deploy(grafana, channel="latest/edge", trust=True)
    await ops_test.model.deploy(
        prometheus_scrape,
        channel="latest/beta",
        config=scrape_config)

    await ops_test.model.add_relation(application_name, prometheus_scrape)
    await ops_test.model.add_relation(
        f"{prometheus}:grafana-dashboard", f"{grafana}:grafana-dashboard"
    )
    await ops_test.model.add_relation(
        f"{application_name}:grafana-dashboard", f"{grafana}:grafana-dashboard"
    )
    await ops_test.model.add_relation(
        f"{prometheus}:metrics-endpoint", f"{prometheus_scrape}:metrics-endpoint"
    )

    await ops_test.model.wait_for_idle(status="active", timeout=60 * 10)

    status = await ops_test.model.get_status()
    prometheus_unit_ip = status["applications"][prometheus]["units"][f"{prometheus}/0"][
        "address"
    ]
    log.info(f"Prometheus available at http://{prometheus_unit_ip}:9090")

    r = requests.get(
        f'http://{prometheus_unit_ip}:9090/api/v1/query?query=up{{juju_application="{application_name}"}}'
    )
    response = json.loads(r.content.decode("utf-8"))
    response_status = response["status"]
    log.info(f"Response status is {response_status}")
    assert response_status == "success"

    response_metric = response["data"]["result"][0]["metric"]
    assert response_metric["juju_application"] == application_name
    assert response_metric["juju_model"] == ops_test.model_name
