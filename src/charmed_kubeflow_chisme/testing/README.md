
<a href="src/charmed_kubeflow_chisme/testing/_unit_tests.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `_unit_tests.py`
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


---

<a href="src/charmed_kubeflow_chisme/testing/_unit_tests.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `test_leadership_events`

```python
test_leadership_events(harness)
```

Test leader-elected event handling. 

Tests if the unit raises correct status: 

* `WaitingStatus` when it's not a leader 

* when elected as the leader, it should leave `WaitingStatus` 

* `WaitingStatus` when another unit is elected as the leader. 



**Args:**
 
 - <b>`harness`</b>:  instantiated Charmed Operator Framework test harness 


---

<a href="src/charmed_kubeflow_chisme/testing/_unit_tests.py#L66"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `test_missing_image`

```python
test_missing_image(
    harness,
    expected_status=<class 'ops.model.BlockedStatus'>,
    leader_check=True
)
```

Tests if the unit raises an expected status when a required oci image is missing in a charm with the following checks order: 

1) check for leadership (optional) 

2) check oci image 



**Args:**
 
 - <b>`harness`</b>:  instantiated Charmed Operator Framework test harness 
 - <b>`expected_status`</b>:  a subclass of `ops.model.StatusBase`. Default: `BlockedStatus` 
 - <b>`leader_check`</b>:  whether the unit should be set to leader first. Default: True 


---

<a href="src/charmed_kubeflow_chisme/testing/_unit_tests.py#L85"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `test_missing_relation`

```python
test_missing_relation(
    harness,
    expected_status=<class 'ops.model.BlockedStatus'>,
    leader_check=True,
    oci_image_added=True
)
```

Checks if the unit raises an expected status when a required relation is missing in a charm with the following checks order: 

1) check for leadership (optional) 

2) check oci image (optional) 

3) check relation 



**Args:**
 
 - <b>`harness`</b>:  instantiated Charmed Operator Framework test harness 
 - <b>`expected_status`</b>:  a subclass of `ops.model.StatusBase`. Default: `BlockedStatus` 
 - <b>`leader_check`</b>:  whether the unit should be set to leader first. Default: True 
 - <b>`oci_image_added`</b>:  whether an oci image resource should be added. Default: True 


---

<a href="src/charmed_kubeflow_chisme/testing/_unit_tests.py#L120"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `test_image_fetch`

```python
test_image_fetch(harness, oci_resource_data)
```

A parametrized image fetching test: 

* the unit should raise MissingResourceError if the oci image is missing 

* no error should be raised if the oci image is in place. 



**Args:**
 
 - <b>`harness`</b>:  instantiated Charmed Operator Framework test harness 
 - <b>`oci_resource_data`</b>:  OCI image details 


---

<a href="src/charmed_kubeflow_chisme/testing/_unit_tests.py#L140"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `test_not_kubeflow_model`

```python
test_not_kubeflow_model(harness)
```

Tests if the unit gets blocked if deployed outside a model named `kubeflow`. 

This test is useful for kubeflow-dashboard-operator and related charms, such as kubeflow-profiles-operator. 



**Args:**
 
 - <b>`harness`</b>:  instantiated Charmed Operator Framework test harness 



