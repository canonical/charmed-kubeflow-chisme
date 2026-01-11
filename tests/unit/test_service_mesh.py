# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from charmed_kubeflow_chisme.service_mesh import (
    generate_allow_all_authorization_policy,
)


def test_policy_has_correct_namespace():
    """Test that the generated policy has the correct namespace."""
    app_name = "test"
    namespace = "test-namespace"
    ap = generate_allow_all_authorization_policy(app_name, namespace)
    assert ap.metadata is not None
    assert ap.metadata.namespace == namespace


def test_policy_targets_correct_workload():
    """Test that the generated policy targets the correct workload."""
    app_name = "test"
    namespace = "test-namespace"
    ap = generate_allow_all_authorization_policy(app_name, namespace)
    assert ap["spec"]["selector"]["matchLabels"]["app.kubernetes.io/name"] == app_name
