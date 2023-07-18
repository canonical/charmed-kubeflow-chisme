# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from fixtures import MinimallyExtendedComponent, harness  # noqa: F401

from charmed_kubeflow_chisme.components.charm_reconciler import CharmReconciler
from charmed_kubeflow_chisme.components.component_graph import ComponentGraph

# TODO: Add tests for execute_components, install, remove_components


class TestBasicFunction:
    def test_init_with_component_graph(self, harness):  # noqa: F811
        """Test that initialising a CharmReconciler with a ComponentGraph works as expected."""
        # Arrange
        charm = harness.charm

        component_graph = ComponentGraph()
        component_graph.add(MinimallyExtendedComponent(charm=charm, name="component"))

        # Act
        charm_reconciler = CharmReconciler(charm, component_graph)

        # Assert
        assert charm_reconciler._component_graph == component_graph

    def test_init_without_component_graph(self, harness):  # noqa: F811
        """Test that initialising a CharmReconciler without a ComponentGraph works as expected."""
        # Arrange
        charm = harness.charm

        # Act
        charm_reconciler = CharmReconciler(charm)

        # Assert that we have a new ComponentGraph automatically created
        assert isinstance(charm_reconciler._component_graph, ComponentGraph)

    def test_add_component(self, harness):  # noqa: F811
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
