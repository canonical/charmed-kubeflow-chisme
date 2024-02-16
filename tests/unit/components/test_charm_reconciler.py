# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import MagicMock

import pytest
from fixtures import MinimallyBlockedComponent, MinimallyExtendedComponent, harness  # noqa: F401
from ops import ActiveStatus, BlockedStatus, WaitingStatus

from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.component_graph import ComponentGraph

# TODO: Add tests for execute_components, install, remove_components


class TestBasicFunction:
    def test_init_with_component_graph(self, harness):
        """Test that initialising a CharmReconciler with a ComponentGraph works as expected."""
        # Arrange
        charm = harness.charm

        component_graph = ComponentGraph()
        component_graph.add(MinimallyExtendedComponent(charm=charm, name="component"))

        # Act
        charm_reconciler = CharmReconciler(charm, component_graph)

        # Assert
        assert charm_reconciler._component_graph == component_graph

    def test_init_without_component_graph(self, harness):
        """Test that initialising a CharmReconciler without a ComponentGraph works as expected."""
        # Arrange
        charm = harness.charm

        # Act
        charm_reconciler = CharmReconciler(charm)

        # Assert that we have a new ComponentGraph automatically created
        assert isinstance(charm_reconciler._component_graph, ComponentGraph)

    def test_add_component(self, harness):
        """Test that adding Components to a CharmReconciler works as expected."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm)

        component1 = MinimallyExtendedComponent(charm=charm, name="component1")
        component2 = MinimallyExtendedComponent(charm=charm, name="component2")

        # Act
        component_graph_item1 = charm_reconciler.add(component1)
        component_graph_item2 = charm_reconciler.add(
            component2, depends_on=[component_graph_item1]
        )

        # Assert
        assert component_graph_item2.depends_on[0] == component_graph_item1
        assert component_graph_item1.name in charm_reconciler._component_graph.component_items
        assert component_graph_item2.name in charm_reconciler._component_graph.component_items
        assert len(charm_reconciler._component_graph.component_items) == 2

    def test_add_component_after_install(self, harness):
        """Test that calling .add() after .install() correctly raises an Exception."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm)
        charm_reconciler.install_default_event_handlers()
        with pytest.raises(RuntimeError):
            charm_reconciler.add("dummy input")

    def test_install_twice(self, harness):
        """Test that calling .install_default_event_handlers twice correctly raises."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm)
        charm_reconciler.install_default_event_handlers()
        with pytest.raises(RuntimeError):
            charm_reconciler.install_default_event_handlers()


class TestUpdateStatus:
    """Tests for CharmReconciler's update status handling."""

    def test_update_status_with_multiple_components_working(self, harness):
        """Tests that update_status works when multiple working components are attached."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm)

        component1 = MinimallyExtendedComponent(charm=charm, name="component1")
        component1._completed_work = True
        component2 = MinimallyExtendedComponent(charm=charm, name="component2")
        component2._completed_work = True
        component_graph_item1 = charm_reconciler.add(component1)
        _ = charm_reconciler.add(component2, depends_on=[component_graph_item1])

        # Act
        charm_reconciler.update_status(MockEvent("abc"))

        # Assert
        assert isinstance(harness.charm.unit.status, ActiveStatus)

    def test_update_status_with_multiple_components_first_not_active(self, harness):
        """Tests that update_status does not go Active when a component is not Active."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm, reconcile_on_update_status=False)

        component1 = MinimallyExtendedComponent(charm=charm, name="component1")
        component1._completed_work = False
        component2 = MinimallyExtendedComponent(charm=charm, name="component2")
        component2._completed_work = True
        component_graph_item1 = charm_reconciler.add(component1)
        _ = charm_reconciler.add(component2, depends_on=[component_graph_item1])

        # Act
        charm_reconciler.update_status(MockEvent("event"))

        # Assert
        assert isinstance(harness.charm.unit.status, WaitingStatus)
        assert f"{component1.name} waiting" in harness.charm.unit.status.message

    def test_update_status_with_multiple_components_second_not_active(self, harness):
        """Tests that update_status does not go Active when a component is not Active."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm, reconcile_on_update_status=False)

        component1 = MinimallyExtendedComponent(charm=charm, name="component1")
        component1._completed_work = True
        component2 = MinimallyBlockedComponent(charm=charm, name="component2")
        component_graph_item1 = charm_reconciler.add(component1)
        _ = charm_reconciler.add(component2, depends_on=[component_graph_item1])

        # Act
        charm_reconciler.update_status(MockEvent("event"))

        # Assert
        assert isinstance(harness.charm.unit.status, BlockedStatus)

    def test_update_status_with_reconcile_true(self, harness):
        """Test that if reconcile_on_update_status=True, update-status triggers a reconcile."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm, reconcile_on_update_status=True)
        charm_reconciler.reconcile = MagicMock()

        # Act
        charm_reconciler.update_status(MockEvent("event"))

        # Assert
        charm_reconciler.reconcile.assert_called()

    def test_update_status_with_reconcile_false(self, harness):
        """Test that if reconcile_on_update_status=False, update-status does not reconcile."""
        # Arrange
        charm = harness.charm

        charm_reconciler = CharmReconciler(charm, reconcile_on_update_status=False)
        charm_reconciler.reconcile = MagicMock()

        # Act
        charm_reconciler.update_status(MockEvent("event"))

        # Assert
        charm_reconciler.reconcile.assert_not_called()


class MockEvent:
    """Mock for an ops.EventBase."""

    def __init__(self, handle):
        """Mock for an ops.EventBase."""
        self.handle = handle
