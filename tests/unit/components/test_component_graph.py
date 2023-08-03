# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from fixtures import (  # noqa: F401
    MinimallyBlockedComponent,
    MinimallyExtendedComponent,
    harness,
)
from ops import BlockedStatus, UnknownStatus

from charmed_kubeflow_chisme.components.component_graph import ComponentGraph
from charmed_kubeflow_chisme.components.component_graph_item import ComponentGraphItem


class TestAdd:
    def test_add_new_components_succeeds(self, harness):
        """Tests that adding a new Component succeeds as expected."""
        cg = ComponentGraph()
        name = "component1"
        cgi1 = cg.add(
            component=MinimallyExtendedComponent(charm=harness, name=name),
            depends_on=[],
        )

        assert isinstance(cgi1, ComponentGraphItem)

        name = "component2"
        cgi2 = cg.add(
            component=MinimallyExtendedComponent(charm=harness, name=name),
            depends_on=[cgi1],
        )

        name = "component3"
        cgi3 = cg.add(
            component=MinimallyExtendedComponent(charm=harness, name=name),
            depends_on=[cgi1, cgi2],
        )

        assert cgi3.name == name
        assert len(cgi3.depends_on) == 2

    def test_add_existing_item_raises(self, harness):
        """Tests that adding two Components of the same name raises an Exception."""

        class MockComponent:
            # Use a mocked Component rather than a real Component because you cannot register two
            # framework Objects of the same name to the same framework.  If we try to create two
            # Components here of the same name, we will get a RuntimeError from the harness.
            name = "component"

        cg = ComponentGraph()
        cg.add(component=MockComponent())
        with pytest.raises(ValueError):
            cg.add(component=MockComponent())


class TestGetExecutableComponentItems:
    """Tests for ComponentGraph.get_executable_component_items."""
    def test_when_component_graph_is_empty(self):
        """Test that an empty graph works as expected."""
        cg = ComponentGraph()
        assert len(cg.get_executable_component_items()) == 0

    def test_when_component_graph_has_mix_of_executable_and_not_executable(self, harness):
        """Test that a populated graph works as expected."""
        cg = ComponentGraph()
        name = "component1"
        cgi1 = cg.add(component=MinimallyExtendedComponent(harness.charm, name), depends_on=[])

        name = "component2"
        cg.add(component=MinimallyExtendedComponent(harness.charm, name), depends_on=[cgi1])

        name = "component3"
        cg.add(component=MinimallyExtendedComponent(harness.charm, name), depends_on=[cgi1])

        # Assert that we have one cgi ready for execution (cgi1)
        executable_cgis = cg.get_executable_component_items()
        assert len(executable_cgis) == 1
        assert executable_cgis[0] == cgi1

        # "execute" cgi1, then check if cgi2 and cgi3 are executable
        cgi1.component.configure_charm("mock event")
        cgi1.executed = True
        executable_cgis = cg.get_executable_component_items()
        assert len(executable_cgis) == 2


class TestStatus:
    """Tests for ComponentGraph.status"""
    def test_no_items(self):
        """Tests that the Status of an empty ComponentGraph is UnknownStatus."""
        cg = ComponentGraph()
        assert isinstance(cg.status, UnknownStatus)

    def test_with_items(self, harness):
        """Tests that the Status of a ComponentGraph with items is returned correctly."""
        cg = ComponentGraph()

        # Add a Component that is Active
        name = "cgi-active"
        cgi_active = cg.add(
            component=MinimallyExtendedComponent(harness.charm, name),
        )
        # "execute" it to make it active
        cgi_active.executed = True
        cgi_active.component.configure_charm("mock event")

        # Add a Component that is Blocked
        name = "cgi-blocked"
        cgi_blocked = cg.add(
            component=MinimallyBlockedComponent(harness.charm, name),
        )
        cgi_blocked.executed = True

        # Add a Component that is Waiting
        name = "cgi-waiting"
        cgi_waiting = cg.add(
            component=MinimallyExtendedComponent(harness.charm, name),
        )
        cgi_waiting.executed = True

        assert isinstance(cg.status, BlockedStatus)


class TestYieldExecutableComponentItems:
    """Tests for ComponentGraph.yield_executable_component_items."""
    def test_no_items(self):
        """Tests that the generator does not yield anything if there are no items."""
        cg = ComponentGraph()
        with pytest.raises(StopIteration):
            next(cg.yield_executable_component_items())

    def test_no_executable_items(self, harness):
        """Tests that the generator does not yield anything if there is nothing executable."""
        cg = ComponentGraph()
        name = "component1"
        cgi1 = cg.add(component=MinimallyExtendedComponent(harness, name), depends_on=[])
        cgi1.executed = True

        with pytest.raises(StopIteration):
            next(cg.yield_executable_component_items())

    def test_with_several_component_items(self, harness):
        """An end-to-end style test of ComponentGraph.yield_executable_component_items()."""
        cg = ComponentGraph()
        name = "component1"
        cgi1 = cg.add(component=MinimallyExtendedComponent(harness.charm, name), depends_on=[])

        name = "component2"
        cgi2 = cg.add(component=MinimallyExtendedComponent(harness.charm, name), depends_on=[cgi1])

        name = "component3"
        cgi3 = cg.add(component=MinimallyExtendedComponent(harness.charm, name), depends_on=[cgi1])

        name = "component4"
        cgi4 = cg.add(
            component=MinimallyExtendedComponent(harness.charm, name), depends_on=[cgi2, cgi3]
        )

        cgi_generator = cg.yield_executable_component_items()

        # Assert that we first get cgi1
        assert next(cgi_generator) == cgi1

        # Assert that we don't have anything else ready for execution yet
        assert len(cg.get_executable_component_items()) == 0

        # If we "execute" cgi1, cgi2 and cgi3 should be yielded next
        cgi1.executed = True
        cgi1.component.configure_charm("mock event")

        assert next(cgi_generator) == cgi2
        assert next(cgi_generator) == cgi3

        # And cgi4 should not be available
        assert len(cg.get_executable_component_items()) == 0

        # Even if one of cgi2 and cgi3 are "executed"
        cgi3.executed = True
        cgi3.component.configure_charm("mock event")

        assert len(cg.get_executable_component_items()) == 0

        # But cgi4 will yield if all prerequisites are ready
        cgi2.executed = True
        cgi2.component.configure_charm("mock event")

        assert next(cgi_generator) == cgi4

        # And now the generator should be empty
        with pytest.raises(StopIteration):
            next(cgi_generator)


class TestEventsToObserve:
    """Tests for ComponentGraph.events_to_observe."""
    def test_if_empty(self):
        """Test that events_to_observe works if graph is empty."""
        cg = ComponentGraph()
        assert len(cg.get_events_to_observe()) == 0

    def test_with_events_to_observe(self, harness):
        """Test that events_to_observe works if graph is populated."""
        cg = ComponentGraph()

        component1 = MinimallyExtendedComponent(harness, "test1")
        events1 = ["event1", "event1b"]
        component1._events_to_observe = events1
        cg.add(component=component1)

        component2 = MinimallyExtendedComponent(harness, "test2")
        events2 = ["event2"]
        component2._events_to_observe = events2
        cg.add(component=component2)

        expected_events = events1 + events2
        assert cg.get_events_to_observe() == expected_events
