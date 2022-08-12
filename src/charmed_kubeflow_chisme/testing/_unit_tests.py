# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from contextlib import nullcontext as does_not_raise

import pytest
from oci_image import MissingResourceError
from ops.model import WaitingStatus


def test_leadership_events(harness):
    """Test leader-elected event handling."""
    harness.set_leader(False)
    harness.begin_with_initial_hooks()
    assert harness.charm.model.unit.status == WaitingStatus("Waiting for leadership")
    harness.set_leader(True)
    assert harness.charm.model.unit.status != WaitingStatus("Waiting for leadership")
    harness.set_leader(False)
    # Emit another leader_elected event due to https://github.com/canonical/operator/issues/812
    harness._charm.on.leader_elected.emit()
    assert harness.charm.model.unit.status == WaitingStatus("Waiting for leadership")


def test_image_fetch(harness, oci_resource_data):
    """Test image fetching.

    The unit should raise MissingResourceError if no image was added.
    """
    harness.begin()
    with pytest.raises(MissingResourceError):
        harness.charm.image.fetch()

    harness.add_oci_resource(**oci_resource_data)
    with does_not_raise():
        harness.charm.image.fetch()
