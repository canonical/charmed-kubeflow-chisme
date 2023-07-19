# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest import mock

from fixtures import (  # noqa: F401
    MinimalPebbleComponent,
    MinimalPebbleServiceComponent,
    harness_with_container,
)
from ops import ActiveStatus, WaitingStatus

import charmed_kubeflow_chisme.components.pebble_component


class TestPebbleComponent:
    name = "test-component"
    container_name = "test-container"

    def test_ready_for_execution_if_service_up(self, harness_with_container):  # noqa: F811
        """Test that ready_for_execution returns True if the service is up."""
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert pc.ready_for_execution is True

    def test_ready_for_execution_if_service_not_up(self, harness_with_container):  # noqa: F811
        """Test that ready_for_execution returns False if the service is up."""
        harness_with_container.set_can_connect(self.container_name, False)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert pc.ready_for_execution is False

    def test_status_if_container_ready(self, harness_with_container):  # noqa: F811
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert isinstance(pc.status, ActiveStatus)

    def test_status_if_container_not_ready(self, harness_with_container):  # noqa: F811
        harness_with_container.set_can_connect(self.container_name, False)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert isinstance(pc.status, WaitingStatus)


class TestPebbleServiceComponent:
    name = "test-component"
    container_name = "test-container"

    def test_configure_charm(self, harness_with_container):  # noqa: F811
        """Test that, if a charm's container is ready, the pebble layer is updated/replanned.

        This test feels weak.  We rely on the object we're testing to give us the expected
        result, and we don't actually assert that we're replanned.  Not sure how to mock this
        better.
        """
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )
        services_expected = pc.get_layer().services

        pc.configure_charm("mock event")

        services_actual = harness_with_container.get_container_pebble_plan(
            self.container_name
        ).services
        assert services_expected == services_actual

    def test_configure_charm_if_container_not_ready(self, harness_with_container):  # noqa: F811
        """Test that, if a charm's container is not ready, we do not update our layer/replan."""
        harness_with_container.set_can_connect(self.container_name, False)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )

        with mock.patch.object(
            charmed_kubeflow_chisme.components.pebble_component, "logging"
        ) as mock_logger:
            pc.configure_charm("mock event")
            mock_logger.info.assert_called_once()
            assert f"Container {self.container_name}" in mock_logger.info.call_args_list[0].args[0]

    def test_get_services_not_active_if_container_not_ready(
        self, harness_with_container  # noqa: F811
    ):
        """Test that get_services_not_active returns all services when container not ready."""
        harness_with_container.set_can_connect(self.container_name, False)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )
        service_names_not_active_expected = ["test-service"]

        services_not_active = pc.get_services_not_active()
        service_names_not_active = [service.name for service in services_not_active]

        assert service_names_not_active_expected == service_names_not_active

    def test_get_services_not_active_if_container_ready_services_not_started(
        self, harness_with_container  # noqa: F811
    ):
        """Test that get_services_not_active returns all services when services not started."""
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )
        service_names_not_active_expected = ["test-service"]

        services_not_active = pc.get_services_not_active()
        service_names_not_active = [service.name for service in services_not_active]

        assert service_names_not_active_expected == service_names_not_active

    def test_get_services_not_active_if_container_ready_services_active(
        self, harness_with_container  # noqa: F811
    ):
        """Test that get_services_not_active returns empty list when services are started."""
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )
        # configure_charm to activate all services.  There's probably a better mock way to do this
        pc.configure_charm("mock event")
        services_not_active_expected = []

        services_not_active = pc.get_services_not_active()

        assert services_not_active_expected == services_not_active

    def test_status_container_not_ready(self, harness_with_container):  # noqa: F811
        """Test that status is Waiting if container not ready."""
        harness_with_container.set_can_connect(self.container_name, False)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )

        status = pc.status

        assert isinstance(status, WaitingStatus)
        assert "Waiting for Pebble to" in pc.status.message

    def test_status_container_ready_service_not_active(self, harness_with_container):  # noqa: F811
        """Test that status is Waiting if services not ready."""
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )

        status = pc.status

        assert isinstance(status, WaitingStatus)
        assert "Waiting for Pebble services (" in pc.status.message

    def test_status_container_ready_service_active(self, harness_with_container):  # noqa: F811
        """Test that status is Active if container is ready and services are active."""
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleServiceComponent(
            charm=harness_with_container.charm,
            name=self.name,
            container_name=self.container_name,
            service_name="test-service",
        )
        # configure_charm to activate all services.  There's probably a better mock way to do this
        pc.configure_charm("mock event")

        status = pc.status

        assert isinstance(status, ActiveStatus)
