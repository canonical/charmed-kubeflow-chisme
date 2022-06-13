# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from contextlib import nullcontext
from pathlib import Path
from unittest import mock

import pytest
from lightkube.models.apps_v1 import StatefulSetSpec, StatefulSetStatus
from lightkube.models.core_v1 import PodTemplateSpec
from lightkube.models.meta_v1 import LabelSelector, ObjectMeta
from lightkube.resources.apps_v1 import StatefulSet
from lightkube.resources.core_v1 import Service
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from utilities import mocked_lightkube_client_class  # Imports a fixture # noqa 401

from k8s_resource_handler import kubernetes
from k8s_resource_handler.exceptions import (
    ErrorWithStatus,
    ReconcileError,
    ReplicasNotReadyError,
    ResourceNotFoundError,
)
from k8s_resource_handler.kubernetes import _check_resources
from k8s_resource_handler.kubernetes._check_resources import _get_resource_or_error
from k8s_resource_handler.kubernetes._validate_statefulset import validate_statefulset
from k8s_resource_handler.lightkube.mocking import FakeApiError

data_dir = Path(__file__).parent.joinpath("data")

statefulset_with_replicas = StatefulSet(
    metadata=ObjectMeta(name="has-replicas", namespace="namespace"),
    spec=StatefulSetSpec(
        replicas=3, selector=LabelSelector(), serviceName="", template=PodTemplateSpec()
    ),
    status=StatefulSetStatus(replicas=3, readyReplicas=3),
)

statefulset_missing_replicas = StatefulSet(
    metadata=ObjectMeta(name="missing-replicas", namespace="namespace"),
    spec=StatefulSetSpec(
        replicas=3, selector=LabelSelector(), serviceName="", template=PodTemplateSpec()
    ),
    status=StatefulSetStatus(replicas=1, readyReplicas=1),
)


@pytest.mark.parametrize(
    "resource,expected_validation,context_raised",
    (
        (statefulset_with_replicas, True, nullcontext()),
        (statefulset_missing_replicas, None, pytest.raises(ReplicasNotReadyError)),
        ("wrong input", None, pytest.raises(AttributeError)),
    ),
)
def test_validate_statefulset(resource, expected_validation, context_raised):
    with context_raised:
        validation = validate_statefulset(resource=resource)
        assert validation == expected_validation


statefulset_dummy = StatefulSet(
    metadata=ObjectMeta(name="has-replicas", namespace="namespace"),
)


@pytest.mark.parametrize(
    "resource,client_get_side_effect,expected_return,context_raised",
    (
        (statefulset_dummy, [statefulset_dummy], statefulset_dummy, nullcontext()),
        (statefulset_dummy, FakeApiError(403), None, pytest.raises(ResourceNotFoundError)),
    ),
)
def test__get_resource_or_error(resource, client_get_side_effect, expected_return, context_raised):
    """Tests _get_resource_or_error.

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


@pytest.mark.parametrize(
    "get_resource_or_error_side_effect,expected_status,expected_errors",
    (
        (  # Case where resources are working
            ["working resource, not a statefulset", "working resource, not a statefulset"],
            True,
            [None, None],
        ),
        (  # Case where get_resource_or_error raises a ResourceNotFoundError
            [ResourceNotFoundError("", BlockedStatus)],
            False,
            [ResourceNotFoundError("", BlockedStatus)],
        ),
        (  # Case where a working StatefulSet is returned
            [statefulset_with_replicas],
            True,
            [None],
        ),
        (  # Case where a StatefulSet that is not ready is returned
            [statefulset_missing_replicas],
            False,
            [ReplicasNotReadyError("", BlockedStatus)],
        ),
    ),
)
def test_check_resources(
    get_resource_or_error_side_effect, expected_status, expected_errors, mocker
):
    # Number of statefulsets that we will be passed (statefulset is a special case that is treated
    # differently)
    n_statefulset = sum(isinstance(x, StatefulSet) for x in get_resource_or_error_side_effect)

    # "resources" to pass check_resources (their content doesn't matter, but their length must
    # match the returns we simulate for get_resource_or_error)
    dummy_input_resources = [None] * len(get_resource_or_error_side_effect)

    # Mock away _get_resource_or_error and spy on validate_statefulset
    # (spy still works like the original, but lets us do things like assert times called)
    mocked_get_resource_or_error = mocker.patch(
        "k8s_resource_handler.kubernetes._check_resources._get_resource_or_error"
    )
    mocked_get_resource_or_error.side_effect = get_resource_or_error_side_effect
    validate_statefulset_spy = mocker.spy(_check_resources, "validate_statefulset")

    # Execute the function under test
    status, errors = kubernetes.check_resources(
        client="fake client",
        resources=dummy_input_resources,
    )

    # Assert our expectations
    assert status == expected_status

    assert len(errors) == len(expected_errors)
    for error, expected_error in zip(errors, expected_errors):
        if error is not None:
            assert isinstance(error, expected_error.__class__)

    # For every statefulset, assert that we reached validate_statefulset
    assert validate_statefulset_spy.call_count == n_statefulset


@pytest.fixture()
def mocked_khr_check_resources(mocker):
    """Mocks check_resources used by the KubernetesResourceHandler."""
    mocked = mocker.patch(
        "k8s_resource_handler.kubernetes._kubernetes_resource_handler.check_resources"
    )
    mocked.return_value = (None, None)
    yield mocked


@pytest.mark.parametrize(
    "resources,is_render_manifests_called",
    (
        (None, True),  # No resources provided, thus render_manifests is called once
        (["a resource"], False),  # Resources provided, thus render_manifests is not called
        ([], False),  # empty list is a valid input of resources, so render_manifest not called
    ),
)
def test_KubernetesResourceHandler_compute_unit_status_inferred_resources(  # noqa N802
    resources,
    is_render_manifests_called,
    mocked_lightkube_client_class,  # noqa F811
    mocked_khr_check_resources,
):
    """Tests whether KRH.compute_unit_status handles cases where no resources are passed."""
    krh = kubernetes.KubernetesResourceHandler(
        template_files_factory=lambda: "",
        context_factory=lambda: {},
        field_manager="field-manager",
    )

    mocked_render_manifests = mock.MagicMock()
    krh.render_manifests = mocked_render_manifests

    mocked_charm_status_given_resource_status = mock.MagicMock()
    mocked_charm_status_given_resource_status.return_value = ActiveStatus()
    krh._charm_status_given_resource_status = mocked_charm_status_given_resource_status

    returned_status = krh.compute_unit_status(resources=resources)

    # Confirm that we hit render_manifests the correct number of times
    assert mocked_render_manifests.call_count == int(is_render_manifests_called)

    # Confirm status returned from resource status parser is returned to original called
    assert returned_status == mocked_charm_status_given_resource_status.return_value


@pytest.mark.parametrize(
    "resource_status,errors,expected_returned_status",
    (
        # If resource_status==True then we go to Active
        (True, [], ActiveStatus()),
        # If resource_status==True we ignore any errors passed and still set to Active
        (True, [ErrorWithStatus("", BlockedStatus)], ActiveStatus()),
        # Return the WaitingStatus observed in the error list, ignoring Nones
        (False, [None, ErrorWithStatus("", WaitingStatus), None], WaitingStatus()),
        # Return the BlockedStatus, preferring that over the WaitingStatus
        (
            False,
            [ErrorWithStatus("", WaitingStatus), ErrorWithStatus("", BlockedStatus)],
            BlockedStatus(),
        ),
    ),
)
def test_KubernetesResourceHandler_charm_status_given_resource_status(  # noqa N802
    resource_status, errors, expected_returned_status
):
    krh = kubernetes.KubernetesResourceHandler(
        template_files_factory=lambda: "",
        context_factory=lambda: {},
        field_manager="field-manager",
    )

    returned_status = krh._charm_status_given_resource_status(
        resource_status=resource_status, errors=errors
    )

    assert returned_status == expected_returned_status


def test_KubernetesResourceHandler_render_manifests():  # noqa N802
    template_files_factory = mock.MagicMock()
    template_files_factory.return_value = [
        data_dir / "template_yaml_0.j2",
        data_dir / "template_yaml_1.j2",
    ]

    context = {
        "port": 8080,
        "selector": "my-nginx",
    }

    def _context_factory():
        return context

    krh = kubernetes.KubernetesResourceHandler(
        template_files_factory=template_files_factory,
        context_factory=_context_factory,
        field_manager="field-manager",
    )

    resource_manifest = krh.render_manifests()

    for i, r in enumerate(resource_manifest):
        assert isinstance(r, Service)
        assert r.metadata.name == f"template-{i}"
        assert r.spec.ports[0].port == context["port"]
        assert r.spec.selector["run"] == context["selector"]


def test_KubernetesResourceHandler_apply():  # noqa N802
    raise NotImplementedError()


@pytest.mark.parametrize(
    "resources,is_render_manifests_called",
    (
        (None, True),  # No resources provided, thus render_manifests is called once
        (["a resource"], False),  # Resources provided, thus render_manifests is not called
    ),
)
def test_KubernetesResourceHandler_apply(  # noqa N802
    resources,
    is_render_manifests_called,
    mocker,
):
    krh = kubernetes.KubernetesResourceHandler(
        template_files_factory=lambda: "",
        context_factory=lambda: {},
        field_manager="field-manager",
    )

    mocked_render_manifests = mock.MagicMock()
    krh.render_manifests = mocked_render_manifests

    mocked_apply_many = mocker.patch(
        "k8s_resource_handler.kubernetes._kubernetes_resource_handler.apply_many"
    )

    krh.apply(resources)

    assert mocked_render_manifests.call_count == int(is_render_manifests_called)
    mocked_apply_many.assert_called_once()


@pytest.mark.parametrize(
    "error_raised_by_apply_many,overall_context_raised",
    (
        (None, nullcontext()),
        (FakeApiError(400), pytest.raises(FakeApiError)),
        (FakeApiError(403), pytest.raises(ReconcileError)),
    ),
)
def test_KubernetesResourceHandler_apply_on_errors(  # noqa N802
    error_raised_by_apply_many, overall_context_raised, mocker
):
    krh = kubernetes.KubernetesResourceHandler(
        template_files_factory=lambda: "",
        context_factory=lambda: {},
        field_manager="field-manager",
    )

    mocked_apply_many = mocker.patch(
        "k8s_resource_handler.kubernetes._kubernetes_resource_handler.apply_many"
    )
    mocked_apply_many.side_effect = error_raised_by_apply_many
    with overall_context_raised:
        krh.apply()
