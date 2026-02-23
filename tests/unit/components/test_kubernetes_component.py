# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

import pytest
from fixtures import DummyCharm, harness  # noqa: F401
from ops import ActiveStatus, BlockedStatus, MaintenanceStatus

from charmed_kubeflow_chisme.components.kubernetes_component import KubernetesComponent


@pytest.fixture()
def kubernetes_component(harness):
    """Returns a KubernetesComponent with mocked dependencies."""
    harness.set_leader(True)
    component = KubernetesComponent(
        charm=harness.charm,
        name="test-k8s-component",
        resource_templates=["some/template.yaml"],
        krh_resource_types=set(),
        krh_labels={"app": "test"},
        lightkube_client=MagicMock(),
    )
    return component


class TestKubernetesComponentGetStatus:
    """Tests for KubernetesComponent.get_status()."""

    def test_active_when_no_missing_resources(self, kubernetes_component):
        """Returns ActiveStatus when all resources are present."""
        with patch.object(
            kubernetes_component,
            "_get_missing_kubernetes_resources",
            return_value=[],
        ):
            status = kubernetes_component.get_status()
            assert status == ActiveStatus()

    def test_blocked_when_missing_resources(self, kubernetes_component):
        """Returns BlockedStatus when resources are missing."""
        with patch.object(
            kubernetes_component,
            "_get_missing_kubernetes_resources",
            return_value=["missing-resource"],
        ):
            status = kubernetes_component.get_status()
            assert status == BlockedStatus(
                "Not all resources found in cluster.  This may be transient if we haven't tried "
                "to deploy them yet."
            )

    def test_non_leader_always_active(self, harness):
        """Non-leader units always return ActiveStatus without API calls."""
        harness.set_leader(False)
        component = KubernetesComponent(
            charm=harness.charm,
            name="test-k8s-component",
            resource_templates=["some/template.yaml"],
            krh_resource_types=set(),
            krh_labels={"app": "test"},
            lightkube_client=MagicMock(),
        )

        with patch.object(
            component,
            "_get_missing_kubernetes_resources",
        ) as mock_get_missing:
            status = component.get_status()
            assert isinstance(status, ActiveStatus)
            mock_get_missing.assert_not_called()

    def test_sets_maintenance_status_during_resource_check(self, kubernetes_component):
        """Sets MaintenanceStatus during resource check, then returns to Active."""
        status_at_api_call = None

        def capture_status(*args, **kwargs):
            nonlocal status_at_api_call
            status_at_api_call = kubernetes_component._charm.unit.status
            # return [] as _in_left_not_right needs array
            return []

        with patch.object(
            kubernetes_component,
            "_get_kubernetes_resource_handler",
        ) as mock_get_krh:
            mock_krh = MagicMock()
            mock_get_krh.return_value = mock_krh
            # check the status when get_deployed_resources is called.
            mock_krh.get_deployed_resources.side_effect = capture_status
            mock_krh.render_manifests.return_value = []

            status = kubernetes_component.get_status()
            kubernetes_component._charm.unit.status = status

            assert status_at_api_call == MaintenanceStatus("Checking Kubernetes resources")
            assert kubernetes_component._charm.unit.status == ActiveStatus()
