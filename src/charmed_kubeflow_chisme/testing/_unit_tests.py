# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import WaitingStatus


def test_start_without_leadership(harness):
    harness.set_leader(False)
    harness.begin_with_initial_hooks()
    assert harness.charm.model.unit.status == WaitingStatus("Waiting for leadership")
    harness.set_leader(True)
    assert harness.charm.model.unit.status != WaitingStatus("Waiting for leadership")


def test_start_with_leadership(harness):
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    assert harness.charm.model.unit.status != WaitingStatus("Waiting for leadership")
    harness.set_leader(False)
    # Emit another leader_elected event due to https://github.com/canonical/operator/issues/812
    harness._charm.on.leader_elected.emit()
    assert harness.charm.model.unit.status == WaitingStatus("Waiting for leadership")
