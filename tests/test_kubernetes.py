from contextlib import nullcontext
from unittest import mock

import pytest

from lightkube.core.exceptions import ApiError
from lightkube.models.apps_v1 import StatefulSetSpec, StatefulSetStatus
from lightkube.models.core_v1 import PodTemplateSpec
from lightkube.models.meta_v1 import ObjectMeta, LabelSelector
from lightkube.resources.apps_v1 import StatefulSet

from k8s_resource_handler.exceptions import ResourceNotFoundError
from k8s_resource_handler.kubernetes._check_resources import _get_resource_or_error
from k8s_resource_handler.kubernetes._validate_statefulset import validate_statefulset
from k8s_resource_handler.lightkube.mocking import FakeApiError


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


statefulset_dummy = StatefulSet(
    metadata=ObjectMeta(name="has-replicas", namespace="namespace"),
)


@pytest.mark.parametrize(
    "resource,client_get_side_effect,expected_return,context_raised",
    (
        (statefulset_dummy, [statefulset_dummy], statefulset_dummy, nullcontext()),
        (statefulset_dummy, FakeApiError(403), None, pytest.raises(ResourceNotFoundError))
    )
)
def test__get_resource_or_error(resource, client_get_side_effect, expected_return, context_raised):
    """Tests _get_resource_or_error

    Args:
        resource: a lightkube resource object defining what we're asking for from the client
        client_get_side_effect: the side effect of the mocked client.get() used here.  Should be
                                either an exception or a single element iterable of the found
                                resource
        expected_return: The expected return from _get_resource_or_error, if it succeeds
        context_raised: The context the function raises (if there is an exception), or
                        nullcontext()
    """

    client = mock.MagicMock()
    client.get.side_effect = client_get_side_effect

    with context_raised:
        resource_returned = _get_resource_or_error(client, resource)
        assert resource_returned == expected_return
