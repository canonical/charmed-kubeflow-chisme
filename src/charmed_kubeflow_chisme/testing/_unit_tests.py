# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""
# Testing

Tools for unit or integration testing, such as importable and reusable tests.

## Usage example

```python
import pytest
from charm import Operator
from charmed_kubeflow_chisme.testing import test_leadership_events as leadership_events
from charmed_kubeflow_chisme.testing import test_missing_relation as missing_relation
from ops.model import WaitingStatus
from ops.testing import Harness


@pytest.fixture
def harness():
    return Harness(Operator)


def test_leadership_events(harness):
    leadership_events(harness)


def test_missing_relation(harness):
    missing_relation(harness, WaitingStatus, oci_image_added=False)
```
"""

from contextlib import nullcontext as does_not_raise

import pytest
from oci_image import MissingResourceError
from ops.model import BlockedStatus, WaitingStatus


def test_leadership_events(harness):
    """Test leader-elected event handling.

    Tests if the unit raises correct status:

    * `WaitingStatus` when it's not a leader

    * when elected as the leader, it should leave `WaitingStatus`

    * `WaitingStatus` when another unit is elected as the leader.

    Args:
        harness: instantiated Charmed Operator Framework test harness
    """
    harness.set_leader(False)
    harness.begin_with_initial_hooks()
    assert harness.charm.model.unit.status == WaitingStatus("Waiting for leadership")
    harness.set_leader(True)
    assert harness.charm.model.unit.status != WaitingStatus("Waiting for leadership")
    harness.set_leader(False)
    # Emit another leader_elected event due to https://github.com/canonical/operator/issues/812
    harness._charm.on.leader_elected.emit()
    assert harness.charm.model.unit.status == WaitingStatus("Waiting for leadership")


def test_missing_image(harness, expected_status=BlockedStatus, leader_check=True):
    """Tests if the unit raises an expected status when a required oci image is missing
    in a charm with the following checks order:

    1) check for leadership (optional)

    2) check oci image

    Args:
        harness: instantiated Charmed Operator Framework test harness
        expected_status: a subclass of `ops.model.StatusBase`. Default: `BlockedStatus`
        leader_check: whether the unit should be set to leader first. Default: True
    """
    if leader_check:
        harness.set_leader(True)
    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, expected_status)


def test_missing_relation(
    harness, expected_status=BlockedStatus, leader_check=True, oci_image_added=True
):
    """Checks if the unit raises an expected status when a required relation is missing
    in a charm with the following checks order:

    1) check for leadership (optional)

    2) check oci image (optional)

    3) check relation

    Args:
        harness: instantiated Charmed Operator Framework test harness
        expected_status: a subclass of `ops.model.StatusBase`. Default: `BlockedStatus`
        leader_check: whether the unit should be set to leader first. Default: True
        oci_image_added: whether an oci image resource should be added. Default: True
    """
    if leader_check:
        harness.set_leader(True)

    if oci_image_added:
        harness.add_oci_resource(
            "oci-image",
            {
                "registrypath": "image",
                "username": "",
                "password": "",
            },
        )

    harness.begin_with_initial_hooks()
    assert isinstance(harness.charm.model.unit.status, expected_status)


def test_image_fetch(harness, oci_resource_data):
    """A parametrized image fetching test:

    * the unit should raise MissingResourceError if the oci image is missing

    * no error should be raised if the oci image is in place.

    Args:
        harness: instantiated Charmed Operator Framework test harness
        oci_resource_data: OCI image details
    """
    harness.begin()
    with pytest.raises(MissingResourceError):
        harness.charm.image.fetch()

    harness.add_oci_resource(**oci_resource_data)
    with does_not_raise():
        harness.charm.image.fetch()


def test_not_kubeflow_model(harness):
    """Tests if the unit gets blocked if deployed outside a model named `kubeflow`.

    This test is useful for kubeflow-dashboard-operator and related charms,
    such as kubeflow-profiles-operator.

    Args:
        harness: instantiated Charmed Operator Framework test harness
    """
    harness.begin_with_initial_hooks()
    assert harness.charm.model.unit.status == BlockedStatus(
        "kubeflow-dashboard must be deployed to model named `kubeflow`: https://git.io/J6d35"
    )
