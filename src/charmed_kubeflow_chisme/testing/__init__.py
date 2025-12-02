# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Utilities for testing charms."""

from .ambient_integration import (
    ISTIO_BEACON_K8S_APP,
    ISTIO_INGRESS_K8S_APP,
    ISTIO_INGRESS_ROUTE_ENDPOINT,
    ISTIO_K8S_APP,
    SERVICE_MESH_ENDPOINT,
    assert_path_reachable_through_ingress,
    deploy_and_integrate_service_mesh_charms,
    get_http_response,
    integrate_with_service_mesh,
)
from .charm_security_context import (
    ContainerSecurityContext,
    assert_security_context,
    generate_container_securitycontext_map,
    get_pod_names,
)
from .charm_spec import CharmSpec, generate_context_from_charm_spec_list
from .cos_integration import (
    ALERT_RULES_DIRECTORY,
    APP_GRAFANA_DASHBOARD,
    APP_LOGGING,
    APP_METRICS_ENDPOINT,
    GRAFANA_AGENT_APP,
    GRAFANA_AGENT_GRAFANA_DASHBOARD,
    GRAFANA_AGENT_LOGGING_PROVIDER,
    GRAFANA_AGENT_METRICS_ENDPOINT,
    assert_alert_rules,
    assert_grafana_dashboards,
    assert_logging,
    assert_metrics_endpoint,
    deploy_and_assert_grafana_agent,
    get_alert_rules,
    get_grafana_dashboards,
)
from .serialized_data_interface import (
    RelationMetadata,
    add_data_to_sdi_relation,
    add_sdi_relation_to_harness,
)

__all__ = [
    RelationMetadata,
    CharmSpec,
    ContainerSecurityContext,
    assert_security_context,
    generate_container_securitycontext_map,
    get_pod_names,
    add_data_to_sdi_relation,
    add_sdi_relation_to_harness,
    assert_alert_rules,
    assert_grafana_dashboards,
    assert_logging,
    assert_metrics_endpoint,
    deploy_and_assert_grafana_agent,
    generate_context_from_charm_spec_list,
    get_alert_rules,
    get_grafana_dashboards,
    GRAFANA_AGENT_APP,
    GRAFANA_AGENT_METRICS_ENDPOINT,
    GRAFANA_AGENT_GRAFANA_DASHBOARD,
    GRAFANA_AGENT_LOGGING_PROVIDER,
    APP_METRICS_ENDPOINT,
    APP_GRAFANA_DASHBOARD,
    APP_LOGGING,
    ALERT_RULES_DIRECTORY,
    ISTIO_K8S_APP,
    ISTIO_INGRESS_K8S_APP,
    ISTIO_BEACON_K8S_APP,
    ISTIO_INGRESS_ROUTE_ENDPOINT,
    SERVICE_MESH_ENDPOINT,
    deploy_and_integrate_service_mesh_charms,
    integrate_with_service_mesh,
    get_http_response,
    assert_path_reachable_through_ingress,
]
