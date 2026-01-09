# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers for integration with Istio ambient mode service mesh."""

from charmed_service_mesh_helpers.models import (
    Action,
    AuthorizationPolicySpec,
    Rule,
    WorkloadSelector,
)
from lightkube.generic_resource import GenericNamespacedResource
from lightkube.models.meta_v1 import ObjectMeta
from lightkube_extensions.types import AuthorizationPolicy


def generate_allow_all_authorization_policy(
    app_name: str, namespace: str
) -> GenericNamespacedResource:
    """Return an AuthorizationPolicy that allows any workload to talk to specified app.

    Args:
        app_name: name of the app to allow traffic to
        namespace: namespace of the app to allow traffic to
    """
    return AuthorizationPolicy(
        metadata=ObjectMeta(
            name=f"{app_name}-allow-all",
            namespace=namespace,
        ),
        spec=AuthorizationPolicySpec(
            selector=WorkloadSelector(
                matchLabels={"app.kubernetes.io/name": app_name},
            ),
            action=Action.allow,
            rules=[Rule()],
        ).model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
    )
