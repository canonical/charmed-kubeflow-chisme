# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from lightkube.models.core_v1 import ServicePort
from ..lib.charms.observability_libs.v1.kubernetes_service_patch import KubernetesServicePatch
from ..lib.charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

def create_metrics_endpoint(charm, metrics_port:str , metrics_path: str) -> MetricsEndpointProvider:
        metrics_service_port = ServicePort(int(metrics_port), name="metrics-port")
        service_patcher = KubernetesServicePatch(
            charm,
            [metrics_service_port],
            service_name=charm.app.name,
        )

        prometheus_provider = MetricsEndpointProvider(
            charm=charm,
            relation_name="metrics-endpoint",
            jobs=[
                {
                    "metrics_path": metrics_path,
                    "static_configs": [{"targets": ["*:{}".format(metrics_port)]}],
                }
            ],
        )
        return prometheus_provider
