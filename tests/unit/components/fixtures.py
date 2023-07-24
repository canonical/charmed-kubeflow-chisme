# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase, WaitingStatus
from ops.pebble import Layer
from ops.testing import Harness

from charmed_kubeflow_chisme.components.component import Component
from charmed_kubeflow_chisme.components.component_graph_item import ComponentGraphItem
from charmed_kubeflow_chisme.components.pebble_component import (
    PebbleComponent,
    PebbleServiceComponent,
)

COMPONENT_NAME = "component"


class MinimallyExtendedComponent(Component):
    """A minimal example of a complete implementation of the abstract Component class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mock placeholder for state that indicates this Component's work is complete
        self._completed_work = None

    def get_status(self) -> StatusBase:
        """Returns ActiveStatus if self._completed_work is not Falsey, else WaitingStatus."""
        if not self._completed_work:
            return WaitingStatus("Waiting for execution")

        return ActiveStatus()

    def _configure_unit(self, event):
        """Fake doing some work."""
        self._completed_work = "some work"


class MinimallyBlockedComponent(MinimallyExtendedComponent):
    """A minimal Component that defaults to being Blocked."""

    @property
    def status(self) -> StatusBase:
        """Returns ActiveStatus if self._completed_work is not Falsey, else WaitingStatus."""
        if not self._completed_work:
            return BlockedStatus("Waiting for execution")

        return ActiveStatus()


class MinimalPebbleComponent(PebbleComponent):
    pass


class MinimalPebbleServiceComponent(PebbleServiceComponent):
    def get_layer(self) -> Layer:
        return Layer(
            {
                "summary": "test-container-layer",
                "services": {
                    self.service_name: {
                        "override": "replace",
                        "summary": "test-service",
                        "startup": "enabled",
                    }
                },
            }
        )


@pytest.fixture()
def component_active_factory():
    """Returns a factory for Components that will be Active."""

    def factory(harness=harness, name=COMPONENT_NAME) -> Component:
        component = MinimallyExtendedComponent(charm=harness.charm, name=name)
        # "execute" the Component, making it now be Active because work has been done
        component.configure_charm("mock event")
        return component

    return factory


@pytest.fixture()
def component_inactive_factory(harness):
    """Returns a factory for Components that will not be Active."""

    def factory(harness=harness, name=COMPONENT_NAME) -> Component:
        return MinimallyExtendedComponent(charm=harness.charm, name=name)

    return factory


@pytest.fixture()
def component_graph_item_factory(harness):
    """Returns a factory for a ComponentGraphItem with a very minimal Component."""

    def factory(harness=harness, name=COMPONENT_NAME) -> ComponentGraphItem:
        return ComponentGraphItem(
            component=MinimallyExtendedComponent(charm=harness.charm, name=name),
        )

    return factory


@pytest.fixture()
def component_graph_item_active_factory(component_active_factory, harness):
    """Returns a factory for a ComponentGraphItem with a very minimal Component that is Active."""

    def factory(harness=harness, name=COMPONENT_NAME) -> ComponentGraphItem:
        cgi = ComponentGraphItem(
            component=component_active_factory(harness=harness, name=name),
        )
        cgi.executed = True
        return cgi

    return factory


@pytest.fixture()
def component_graph_item_with_depends_not_active_factory(component_graph_item_factory, harness):
    """Returns a factory for a ComponentGraphItem that depends on another that is not Active."""

    def factory(harness=harness, name=COMPONENT_NAME) -> ComponentGraphItem:
        return ComponentGraphItem(
            component=MinimallyExtendedComponent(charm=harness.charm, name=name),
            depends_on=[component_graph_item_factory(harness=harness, name="dependency")],
        )

    return factory


@pytest.fixture()
def component_graph_item_with_depends_active_factory(component_graph_item_active_factory, harness):
    """Returns a factory for a ComponentGraphItem that depends on another that is Active."""

    def factory(harness=harness, name=COMPONENT_NAME) -> ComponentGraphItem:
        return ComponentGraphItem(
            component=MinimallyExtendedComponent(charm=harness.charm, name=name),
            depends_on=[component_graph_item_active_factory(harness=harness, name="dependency")],
        )

    return factory


class DummyCharm(CharmBase):
    pass


@pytest.fixture()
def harness():
    harness = Harness(DummyCharm, meta="")
    harness.begin()
    return harness


METADATA_WITH_CONTAINER = """
name: test-charm
containers:
  test-container:
"""


@pytest.fixture()
def harness_with_container():
    harness = Harness(DummyCharm, meta=METADATA_WITH_CONTAINER)
    harness.begin()
    return harness
