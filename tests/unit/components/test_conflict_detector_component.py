# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from fixtures import DummyCharm  # noqa: F401
from ops import ActiveStatus, BlockedStatus
from ops.testing import Harness

from charmed_kubeflow_chisme.components.conflict_detector_component import (
    ConflictDetectorComponent,
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


class TestConflictDetectorComponent:
    def test_no_relations_active_returns_active_status(self, harness):
        """When none of the watched relations are present, status should be Active."""
        component = ConflictDetectorComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_one_relation_active_returns_active_status(self, harness):
        """When only one of the watched relations is present, status should be Active."""
        harness.add_relation("relation-a", "remote-app")
        component = ConflictDetectorComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_two_relations_active_returns_blocked_status(self, harness):
        """When two watched relations are simultaneously present, status should be Blocked."""
        harness.add_relation("relation-a", "remote-app-a")
        harness.add_relation("relation-b", "remote-app-b")
        component = ConflictDetectorComponent(
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
        component = ConflictDetectorComponent(
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
        """A relation not in the watch list being active should not affect the status."""
        harness.add_relation("relation-c", "remote-app-c")
        component = ConflictDetectorComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=["relation-a", "relation-b"],
        )
        assert isinstance(component.get_status(), ActiveStatus)

    def test_empty_relation_names_returns_active_status(self, harness):
        """An empty relation_names list should always return Active."""
        component = ConflictDetectorComponent(
            charm=harness.charm,
            name="conflict-detector",
            relation_names=[],
        )
        assert isinstance(component.get_status(), ActiveStatus)
