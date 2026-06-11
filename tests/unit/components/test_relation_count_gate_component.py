# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from fixtures import DummyCharm  # noqa: F401
from ops import ActiveStatus, BlockedStatus
from ops.testing import Harness

from charmed_kubeflow_chisme.components.relation_count_gate_component import (
    RelationCountGateComponent,
)

METADATA_WITH_RELATIONS = """
name: test-charm
requires:
  relation-a:
    interface: interface-a
  relation-b:
    interface: interface-b
  relation-c:
    interface: interface-c
"""


@pytest.fixture()
def harness():
    harness = Harness(DummyCharm, meta=METADATA_WITH_RELATIONS)
    harness.begin()
    return harness


class TestRelationCountGateComponent:
    def test_no_relations_active_returns_blocked_status(self, harness):
        """When none of the watched relations are present, status should be Blocked (min=1)."""
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
        )
        assert isinstance(component.get_status(), BlockedStatus)

    def test_one_relation_active_returns_active_status(self, harness):
        """When only one of the watched relations is present, status should be Active."""
        harness.add_relation("relation-a", "remote-app")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_two_relations_active_returns_blocked_status(self, harness):
        """When two watched relations are simultaneously present, status should be Blocked."""
        harness.add_relation("relation-a", "remote-app-a")
        harness.add_relation("relation-b", "remote-app-b")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
        )
        status = component.get_status()
        assert isinstance(status, BlockedStatus)
        assert "relation-a" in status.message
        assert "relation-b" in status.message

    def test_three_relations_active_returns_blocked_status(self, harness):
        """When all three watched relations are active, status should be Blocked."""
        harness.add_relation("relation-a", "remote-app-a")
        harness.add_relation("relation-b", "remote-app-b")
        harness.add_relation("relation-c", "remote-app-c")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b", "relation-c"],
        )
        status = component.get_status()
        assert isinstance(status, BlockedStatus)
        assert "relation-a" in status.message
        assert "relation-b" in status.message
        assert "relation-c" in status.message

    def test_unlisted_relation_active_does_not_block(self, harness):
        """A relation not in the watch list being active should not count towards the total."""
        harness.add_relation("relation-c", "remote-app-c")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
            minimum_related_applications=0,
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_empty_relation_names_returns_blocked_status(self, harness):
        """An empty relation_names list with default min=1 should always return Blocked."""
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=[],
        )
        assert isinstance(component.get_status(), BlockedStatus)

    # --- maximum_related_applications ---

    def test_explicit_maximum_not_exceeded_returns_active_status(self, harness):
        """When active relations equal the explicit maximum, status should be Active."""
        harness.add_relation("relation-a", "remote-app-a")
        harness.add_relation("relation-b", "remote-app-b")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b", "relation-c"],
            maximum_related_applications=2,
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_explicit_maximum_exceeded_returns_blocked_status(self, harness):
        """When active relations exceed the explicit maximum, status should be Blocked."""
        harness.add_relation("relation-a", "remote-app-a")
        harness.add_relation("relation-b", "remote-app-b")
        harness.add_relation("relation-c", "remote-app-c")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b", "relation-c"],
            maximum_related_applications=2,
        )
        status = component.get_status()
        assert isinstance(status, BlockedStatus)
        assert "relation-a" in status.message
        assert "relation-b" in status.message
        assert "relation-c" in status.message

    def test_maximum_zero_with_no_active_returns_active_status(self, harness):
        """When maximum is 0 and no relations are active, status should be Active."""
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
            minimum_related_applications=0,
            maximum_related_applications=0,
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_maximum_zero_with_one_active_returns_blocked_status(self, harness):
        """When maximum is 0 and one relation is active, status should be Blocked."""
        harness.add_relation("relation-a", "remote-app-a")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
            minimum_related_applications=0,
            maximum_related_applications=0,
        )
        assert isinstance(component.get_status(), BlockedStatus)

    # --- minimum_related_applications ---

    def test_minimum_not_met_returns_blocked_status(self, harness):
        """When fewer relations are active than the minimum, status should be Blocked."""
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
            minimum_related_applications=1,
            maximum_related_applications=2,
        )
        status = component.get_status()
        assert isinstance(status, BlockedStatus)
        assert "relation-a" in status.message
        assert "relation-b" in status.message

    def test_minimum_exactly_met_returns_active_status(self, harness):
        """When active relations exactly equal the minimum, status should be Active."""
        harness.add_relation("relation-a", "remote-app-a")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
            minimum_related_applications=1,
            maximum_related_applications=2,
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_between_minimum_and_maximum_returns_active_status(self, harness):
        """When active relations are within [min, max], status should be Active."""
        harness.add_relation("relation-a", "remote-app-a")
        harness.add_relation("relation-b", "remote-app-b")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b", "relation-c"],
            minimum_related_applications=1,
            maximum_related_applications=2,
        )
        assert isinstance(component.get_status(), ActiveStatus)

    # --- constructor validation ---

    def test_negative_minimum_raises_value_error(self, harness):
        """A negative minimum_related_applications should raise ValueError."""
        with pytest.raises(ValueError, match="minimum_related_applications"):
            RelationCountGateComponent(
                charm=harness.charm,
                name="conflict-detector",
                relation_names=["relation-a"],
                minimum_related_applications=-1,
            )

    def test_negative_maximum_raises_value_error(self, harness):
        """A negative maximum_related_applications should raise ValueError."""
        with pytest.raises(ValueError, match="maximum_related_applications"):
            RelationCountGateComponent(
                charm=harness.charm,
                name="conflict-detector",
                relation_names=["relation-a"],
                maximum_related_applications=-1,
            )

    def test_minimum_exceeds_maximum_raises_value_error(self, harness):
        """minimum_related_applications > maximum_related_applications should raise ValueError."""
        with pytest.raises(ValueError, match="minimum_related_applications"):
            RelationCountGateComponent(
                charm=harness.charm,
                name="conflict-detector",
                relation_names=["relation-a", "relation-b"],
                minimum_related_applications=3,
                maximum_related_applications=2,
            )
