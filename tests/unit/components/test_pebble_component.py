# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from fixtures import (  # noqa: F401
    MinimalPebbleComponent,
    MinimalPebbleServiceComponent,
    harness_with_container,
)
from ops import ActiveStatus, WaitingStatus

import charmed_kubeflow_chisme.components.pebble_component
from charmed_kubeflow_chisme.components import ContainerFileTemplate, LazyContainerFileTemplate


class TestPebbleComponent:
    name = "test-component"
    container_name = "test-container"

    def test_ready_for_execution_if_service_up(self, harness_with_container):
        """Test that ready_for_execution returns True if the service is up."""
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert pc.ready_for_execution is True

    def test_ready_for_execution_if_service_not_up(self, harness_with_container):
        """Test that ready_for_execution returns False if the service is up."""
        harness_with_container.set_can_connect(self.container_name, False)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert pc.ready_for_execution is False

    def test_status_if_container_ready(self, harness_with_container):
        harness_with_container.set_can_connect(self.container_name, True)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert isinstance(pc.status, ActiveStatus)

    def test_status_if_container_not_ready(self, harness_with_container):
        harness_with_container.set_can_connect(self.container_name, False)
        pc = MinimalPebbleComponent(
            charm=harness_with_container.charm, name=self.name, container_name=self.container_name
        )

        assert isinstance(pc.status, WaitingStatus)


class TestPebbleServiceComponent:
    name = "test-component"
    container_name = "test-container"

    def test_configure_charm(self, harness_with_container):
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

    def test_configure_charm_if_container_not_ready(self, harness_with_container):
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

    def test_get_services_not_active_if_container_not_ready(self, harness_with_container):
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
        self, harness_with_container
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
        self, harness_with_container
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

    def test_status_container_not_ready(self, harness_with_container):
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

    def test_status_container_ready_service_not_active(self, harness_with_container):
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

    def test_status_container_ready_service_active(self, harness_with_container):
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


class TestContainerFileTemplate:
    def test_static_inputs(self):
        """Tests that the ContainerFileTemplate can accept static inputs."""
        source_template_path = "source_template_path"
        destination_path = "destination_path"
        context = {"key": "value"}
        user = "user"
        group = "group"
        permissions = "permissions"

        # Test these without using kwargs to ensure they API doesn't change
        cft = ContainerFileTemplate(
            source_template_path,
            destination_path,
            context_function=context,
            user=user,
            group=group,
            permissions=permissions,
        )

        assert cft.destination_path == Path(destination_path)
        assert cft.source_template_path == Path(source_template_path)
        assert cft.context_function() == context
        assert cft.user == user
        assert cft.group == group
        assert cft.permissions == permissions

    def test_lazy_inputs(self):
        """Tests that the ContainerFileTemplate can accept lazy inputs."""
        source_template_path = "source_template_path"
        destination_path = "destination_path"
        context = {"key": "value"}
        user = "user"
        group = "group"
        permissions = "permissions"

        # Test these without using kwargs to ensure the API doesn't change
        cft = ContainerFileTemplate(
            source_template_path,
            destination_path,
            lambda: context,
            user,
            group,
            permissions,
        )

        assert cft.destination_path == Path(destination_path)
        assert cft.source_template_path == Path(source_template_path)
        assert cft.context_function() == context
        assert cft.user == user
        assert cft.group == group
        assert cft.permissions == permissions


class TestLazyContainerFileTemplate:
    def test_static_inputs(self):
        """Tests that the LazyContainerFileTemplate can accept static inputs."""
        destination_path = "destination_path"
        source_template_path = "source_template_path"
        context = {"key": "value"}
        user = "user"
        group = "group"
        permissions = "permissions"

        # Test these without using kwargs to ensure they API doesn't change
        cft = LazyContainerFileTemplate(
            destination_path,
            source_template_path=source_template_path,
            context=context,
            user=user,
            group=group,
            permissions=permissions,
        )

        assert cft.destination_path == Path(destination_path)
        assert cft.source_template_path == Path(source_template_path)
        assert cft.context == context
        assert cft.user == user
        assert cft.group == group
        assert cft.permissions == permissions

    def test_lazy_inputs(self):
        """Tests that the LazyContainerFileTemplate can accept lazy inputs."""
        destination_path = "destination_path"
        source_template_path = "source_template_path"
        context = {"key": "value"}
        user = "user"
        group = "group"
        permissions = "permissions"

        # Test these without using kwargs to ensure they API doesn't change
        cft = LazyContainerFileTemplate(
            destination_path,
            source_template_path=lambda: source_template_path,
            context=lambda: context,
            user=user,
            group=group,
            permissions=permissions,
        )

        assert cft.destination_path == Path(destination_path)
        assert cft.source_template_path == Path(source_template_path)
        assert cft.context == context
        assert cft.user == user
        assert cft.group == group
        assert cft.permissions == permissions

    @pytest.mark.parametrize(
        "source_template, source_template_path",
        [
            (None, None),
            ("not none", "not none"),
        ],
    )
    def test_requires_exactly_one_of_source_template_and_source_template_path(
        self, source_template, source_template_path
    ):
        """Tests LazyContainerFileTemplate requires one of source_template/source_template_path."""
        with pytest.raises(ValueError):
            LazyContainerFileTemplate(
                "destination_path",
                source_template_path=source_template_path,
                source_template=source_template,
                context={},
                user="user",
                group="group",
                permissions="permissions",
            )

    def test_get_source_template_given_source_template(self):
        """Tests get_source_template returns the expected value when provided source_template."""
        source_template = "source_template"
        cft = LazyContainerFileTemplate(
            "destination_path",
            source_template=source_template,
            context={},
            user="user",
            group="group",
            permissions="permissions",
        )

        assert cft.get_source_template() == source_template

    def test_get_source_template_given_source_template_file(self):
        """Tests get_source_template returns expected value when provided source_template_file."""
        source_template = "source_template"
        with tempfile.NamedTemporaryFile() as f:
            f.write(source_template.encode())
            # Ensure the text is written to the file and not kept buffered
            f.flush()
            cft = LazyContainerFileTemplate(
                "destination_path",
                source_template_path=f.name,
                context={},
                user="user",
                group="group",
                permissions="permissions",
            )

            assert cft.get_source_template() == source_template

    def test_render(self):
        """Tests render given a source_template and context."""
        source_template = "unrendered {{ key }} template"
        expected = "unrendered value template"
        cft = LazyContainerFileTemplate(
            "destination_path",
            source_template=source_template,
            context={"key": "value"},
            user="user",
            group="group",
            permissions="permissions",
        )

        assert cft.render() == expected

    def test_get_inputs_for_push(self):
        """Tests get_inputs_for_push returns the expected inputs."""
        source_template = "unrendered {{ key }} template"
        expected_rendered = "unrendered value template"
        user = "user"
        group = "group"
        permissions = "permissions"
        cft = LazyContainerFileTemplate(
            "destination_path",
            source_template=source_template,
            context={"key": "value"},
            user=user,
            group=group,
            permissions=permissions,
        )
        expected = {
            "path": Path("destination_path"),
            "source": expected_rendered,
            "user": user,
            "group": group,
            "permissions": permissions,
            "make_dirs": True,
        }

        assert cft.get_inputs_for_push() == expected
