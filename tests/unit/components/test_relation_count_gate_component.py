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
    @pytest.mark.parametrize(
        "active_relations, relation_names, minimum_related_applications, maximum_related_applications, expected_status",
        [
            # min=1, active=0 -> blocked
            ([], [], 1, 1, BlockedStatus),
            # max=1, active=2 -> blocked
            (["relation-a", "relation-b"], ["relation-a", "relation-b"], 1, 1, BlockedStatus),
            # max=1, active=3 -> blocked
            (
                ["relation-a", "relation-b", "relation-c"],
                ["relation-a", "relation-b", "relation-c"],
                1,
                1,
                BlockedStatus,
            ),
            # min=0, max=1, active=0, 1 unrelated -> active
            (["relation-c"], ["relation-a", "relation-b"], 0, 1, ActiveStatus),
            # max=0, active=0 -> active
            ([], ["relation-a", "relation-b"], 0, 0, ActiveStatus),
            # max=0, active=1 -> blocked
            (["relation-a"], ["relation-a", "relation-b"], 0, 0, BlockedStatus),
            # min=1, active=0 -> blocked
            ([], ["relation-a", "relation-b"], 1, 2, BlockedStatus),
            # min=1, active=1 -> active
            (["relation-a"], ["relation-a", "relation-b"], 1, 2, ActiveStatus),
            # min=1, max=2, active=2 -> active
            (
                ["relation-a", "relation-b"],
                ["relation-a", "relation-b", "relation-c"],
                1,
                2,
                ActiveStatus,
            ),
        ],
    )
    def test_get_status_min_max_active_relations(
        self,
        harness,
        active_relations,
        relation_names,
        minimum_related_applications,
        maximum_related_applications,
        expected_status,
    ):
        """get_status() returns the expected status for the given relation configuration.

        Args:
            harness: Ops testing harness with the charm under test
            active_relations: Current active relations in the charm
            relation_names: Relations to watch for
            minimum_related_applications: Lower bound for the component to be active
            maximum_related_applications: Upper bound for the component to be active
            expected_status: Expected status for the component

        """
        for relation in active_relations:
            harness.add_relation(relation, "remote-app")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=relation_names,
            minimum_related_applications=minimum_related_applications,
            maximum_related_applications=maximum_related_applications,
        )
        assert isinstance(component.get_status(), expected_status)

    def test_get_status_multiple_cardinality_active(self, harness):
        """get_status() returns Active when the same endpoint has 2 instances and max=2."""
        harness.add_relation("relation-a", "remote-app-1")
        harness.add_relation("relation-a", "remote-app-2")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a"],
            minimum_related_applications=1,
            maximum_related_applications=2,
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_get_status_multiple_cardinality_blocked(self, harness):
        """get_status() returns Blocked when the same endpoint has 2 instances but max=1."""
        harness.add_relation("relation-a", "remote-app-1")
        harness.add_relation("relation-a", "remote-app-2")
        component = RelationCountGateComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a"],
            minimum_related_applications=1,
            maximum_related_applications=1,
        )
        assert isinstance(component.get_status(), BlockedStatus)

    @pytest.mark.parametrize(
        "relation_names, minimum_related_applications, maximum_related_applications, match",
        [
            # negative minimum
            (["relation-a"], -1, 1, "minimum_related_applications"),
            # negative maximum
            (["relation-a"], 0, -1, "maximum_related_applications"),
            # minimum exceeds maximum
            (["relation-a", "relation-b"], 3, 2, "minimum_related_applications"),
        ],
    )
    def test_min_max_applications_raises_value_error(
        self,
        harness,
        relation_names,
        minimum_related_applications,
        maximum_related_applications,
        match,
    ):
        """Invalid constructor arguments should raise ValueError."""
        with pytest.raises(ValueError, match=match):
            RelationCountGateComponent(
                charm=harness.charm,
                name="conflict-detector",
                relation_names=relation_names,
                minimum_related_applications=minimum_related_applications,
                maximum_related_applications=maximum_related_applications,
            )
