# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import patch

from fixtures import MinimallyExtendedComponent, harness  # noqa F401
from ops import ActiveStatus, WaitingStatus


class TestMinimallyExtendedComponent:
    def test_status_before_execution(self, harness):  # noqa: F811
        """Tests that the minimal implementation of Component does not raise a syntax error."""
        component = MinimallyExtendedComponent(charm=harness.charm, name="test-component")
        assert isinstance(component.status, WaitingStatus)

    def test_status_after_execution(self, harness):  # noqa: F811
        """Tests that the minimal implementation of Component does not raise a syntax error."""
        component = MinimallyExtendedComponent(charm=harness.charm, name="test-component")
        component.configure_charm("mock event")
        assert isinstance(component.status, ActiveStatus)

    def test_configure_charm_as_leader(self, harness):  # noqa: F811
        harness.set_leader(True)
        component = MinimallyExtendedComponent(charm=harness.charm, name="test-component")

        results = configure_charm_and_spy(component)
        assert results["configure_app_leader"] is True
        assert results["configure_app_non_leader"] is False
        assert results["configure_unit"] is True

    def test_configure_charm_as_non_leader(self, harness):  # noqa: F811
        harness.set_leader(False)
        component = MinimallyExtendedComponent(charm=harness.charm, name="test-component")

        results = configure_charm_and_spy(component)
        assert results["configure_app_leader"] is False
        assert results["configure_app_non_leader"] is True
        assert results["configure_unit"] is True


def configure_charm_and_spy(component):
    """Executes component.configure_charm() and returns whether _configure* methods were called.

    Returns:
        Dict of:
            configure_app_leader: Boolean of whether this method was called
            configure_app_non_leader: Boolean of whether this method was called
            configure_unit: Boolean of whether this method was called
    """
    with (
        patch.object(
            component, "_configure_app_leader", wraps=component._configure_app_leader
        ) as spied_configure_app_leader,
        patch.object(
            component, "_configure_app_non_leader", wraps=component._configure_app_non_leader
        ) as spied_configure_app_non_leader,
        patch.object(
            component, "_configure_unit", wraps=component._configure_unit
        ) as spied_configure_unit,
    ):
        # TODO: Make a real event somehow
        event = "TODO: make this a real event"
        component.configure_charm(event)
        results = {
            "configure_app_leader": spied_configure_app_leader.called,
            "configure_app_non_leader": spied_configure_app_non_leader.called,
            "configure_unit": spied_configure_unit.called,
        }
        return results
