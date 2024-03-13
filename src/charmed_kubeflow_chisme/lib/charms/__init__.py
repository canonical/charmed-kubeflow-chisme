# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities we need from charmcraft libraries."""

from charms.observability_libs.v1.kubernetes_service_patch import KubernetesServicePatch
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

__all__ = [KubernetesServicePatch, MetricsEndpointProvider]
