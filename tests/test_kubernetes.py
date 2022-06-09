from contextlib import nullcontext

import pytest

from lightkube.models.apps_v1 import StatefulSetSpec, StatefulSetStatus
from lightkube.models.core_v1 import PodTemplateSpec
from lightkube.models.meta_v1 import ObjectMeta, LabelSelector
from lightkube.resources.apps_v1 import StatefulSet

from k8s_resource_handler.kubernetes._validate_statefulset import validate_statefulset
from k8s_resource_handler.status_handling import get_first_worst_error


statefulset_with_replicas = StatefulSet(
    metadata=ObjectMeta(name="has-replicas", namespace="namespace"),
    spec=StatefulSetSpec(replicas=3, selector=LabelSelector(), serviceName="", template=PodTemplateSpec()),
    status=StatefulSetStatus(replicas=3, readyReplicas=3),
)

statefulset_missing_replicas = StatefulSet(
    metadata=ObjectMeta(name="missing-replicas", namespace="namespace"),
    spec=StatefulSetSpec(replicas=3, selector=LabelSelector(), serviceName="", template=PodTemplateSpec()),
    status=StatefulSetStatus(replicas=1, readyReplicas=1),
)


@pytest.mark.parametrize(
    "resource,expected_validation,context_raised",
    (
        (statefulset_with_replicas, True, nullcontext()),
        (statefulset_missing_replicas, False, nullcontext()),
        ("wrong input", None, pytest.raises(AttributeError)),
    )
)
def test_validate_statefulset(resource, expected_validation, context_raised):
    with context_raised:
        validation, error = validate_statefulset(resource=resource)
        assert validation == expected_validation
        if validation is not True:
            assert error is not None


