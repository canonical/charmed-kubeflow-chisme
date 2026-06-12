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
    def test_get_status(
        self,
        harness,
        active_relations,
        relation_names,
        minimum_related_applications,
        maximum_related_applications,
        expected_status,
    ):
        """get_status() returns the expected status for the given relation configuration."""
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
