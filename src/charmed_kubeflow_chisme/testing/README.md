# Testing

Tools for unit or integration testing, such as importable and reusable tests.

# Contents

## `test_leadership_events`
Tests if the unit raises correct status:
* `WaitingStatus` when it's not a leader
* when elected as the leader, it should leave `WaitingStatus`
* `WaitingStatus` when another unit is elected as the leader.

## `test_missing_image`
Tests if the unit raises an expected status when a required oci image is missing.

The `expected_status` parameter should be one of:
* `WaitingStatus`
* `BlockedStatus`
* `MaintenanceStatus`
* `ActiveStatus`

## `test_missing_relation`
Checks if the unit raises an expected status when a required oci image was added, but a required relation is missing.

The `expected_status` parameter should be one of:
* `WaitingStatus`
* `BlockedStatus`
* `MaintenanceStatus`
* `ActiveStatus`

## `test_image_fetch`
A parametrized image fetching test:
* the unit should raise MissingResourceError if the oci image is missing
* no error should be raised if the oci image is in place.

## `test_not_kubeflow_model`
Tests if the unit gets blocked if deployed outside a model named `kubeflow`.

This test is useful for kubeflow-dashboard-operator and related charms, such as kubeflow-profiles-operator.

# Usage example
```python
import pytest
from charm import Operator
from charmed_kubeflow_chisme.testing import test_leadership_events as leadership_events
from charmed_kubeflow_chisme.testing import test_missing_image as missing_image
from ops.model import WaitingStatus
from ops.testing import Harness


@pytest.fixture
def harness():
    return Harness(Operator)


def test_leadership_events(harness):
    leadership_events(harness)

    
def test_missing_image(harness):
    missing_image(harness, WaitingStatus)
```
