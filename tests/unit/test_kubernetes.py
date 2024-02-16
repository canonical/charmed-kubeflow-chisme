# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import copy
import logging
from contextlib import nullcontext
from pathlib import Path
from typing import NamedTuple
from unittest import mock

import pytest
from lightkube.generic_resource import create_global_resource, create_namespaced_resource
from lightkube.models.apps_v1 import StatefulSetSpec, StatefulSetStatus
from lightkube.models.core_v1 import PodTemplateSpec
from lightkube.models.meta_v1 import LabelSelector, ObjectMeta
from lightkube.resources.admissionregistration_v1 import MutatingWebhookConfiguration
from lightkube.resources.apps_v1 import StatefulSet
from lightkube.resources.core_v1 import Pod, Service
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

from charmed_kubeflow_chisme import kubernetes
from charmed_kubeflow_chisme.exceptions import (
    ErrorWithStatus,
    ReplicasNotReadyError,
    ResourceNotFoundError,
)
from charmed_kubeflow_chisme.kubernetes import _check_resources
from charmed_kubeflow_chisme.kubernetes._check_resources import _get_resource
from charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler import (
    _add_labels_to_resources,
    _get_resource_classes_in_manifests,
    _hash_lightkube_resource,
    _in_left_not_right,
    _validate_resources,
    codecs,
)
from charmed_kubeflow_chisme.kubernetes._validate_statefulset import validate_statefulset
from charmed_kubeflow_chisme.lightkube.mocking import FakeApiError

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


@pytest.fixture()
def mocked_khr_lightkube_client_class(mocker):
    """Prevents lightkube clients from being created, returning a mock instead."""
    mocked_khr_lightkube_client_class = mocker.patch(
        "charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler.Client"
    )
    mocked_khr_lightkube_client_class.return_value = mock.MagicMock()
    yield mocked_khr_lightkube_client_class


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
def test__get_resource(resource, client_get_side_effect, expected_return, context_raised):
    """Tests _get_resource.

    Args:
        resource: a lightkube resource object defining what we're asking for from the client
        client_get_side_effect: the side effect of the mocked client.get() used here.  Should be
                                either an exception or a single element iterable of the found
                                resource
        expected_return: The expected return from _get_resource, if it succeeds
        context_raised: The context the function raises (if there is an exception), or
                        nullcontext()
    """
    client = mock.MagicMock()
    client.get.side_effect = client_get_side_effect

    with context_raised:
        resource_returned = _get_resource(client, resource)
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

    # Mock away _get_resource and spy on validate_statefulset
    # (spy still works like the original, but lets us do things like assert times called)
    mocked_get_resource = mocker.patch(
        "charmed_kubeflow_chisme.kubernetes._check_resources._get_resource"
    )
    mocked_get_resource.side_effect = get_resource_or_error_side_effect
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


@pytest.mark.parametrize(
    "field_manager,template_files,context,logger,exception_context_raised",
    (
        # With context and template_files defined
        ("fm", ["some-file", "some-other-file"], {"some": "context"}, None, nullcontext()),
        # With context and template_files omitted
        ("fm", None, None, None, nullcontext()),
    ),
)
def test_KubernetesResourceHandler_init(  # noqa: N802
    field_manager, template_files, context, logger, exception_context_raised
):
    with exception_context_raised:
        krh = kubernetes.KubernetesResourceHandler(
            field_manager,
            template_files=template_files,
            context=context,
            logger=logger,
        )

        assert krh.template_files == template_files
        assert krh.context == context
        assert isinstance(krh.log, logging.Logger)
        # If we have one, assert we use the default logger
        if logger is not None:
            assert krh.log is logger


@pytest.fixture()
def simple_krh_instance():
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=["some-file"],
        context={"some": "context"},
    )
    yield krh


@pytest.mark.parametrize(
    "property_name,property_value",
    (
        ("context", None),
        ("context", {"new": "context"}),
        ("template_files", None),
        ("template_files", ["new-file"]),
        ("labels", {}),
        ("labels", {"new": "label"}),
    ),
)
def test_KubernetesResourceHandler_manifest_resetting_properties(  # noqa: N802
    property_name, property_value, simple_krh_instance
):
    """Tests that setting KRH properties correctly deletes any cached manifests."""
    krh = simple_krh_instance

    dummy_manifests = ["some-manifests"]
    krh._manifests = dummy_manifests
    assert krh._manifests == dummy_manifests

    # Changing input param should clear cached _manifests
    setattr(krh, property_name, property_value)
    assert getattr(krh, property_name) == property_value
    assert krh._manifests is None


@pytest.fixture()
def mocked_krh_check_resources(mocker):
    """Mocks check_resources used by the KubernetesResourceHandler."""
    mocked = mocker.patch(
        "charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler.check_resources"
    )
    mocked.return_value = (None, None)
    yield mocked


def test_KubernetesResourceHandler_compute_unit_status(  # noqa N802
    mocked_khr_lightkube_client_class,  # noqa F811
    mocked_krh_check_resources,
    simple_krh_instance,
):
    krh = simple_krh_instance

    # Dummy that will be returned from render_manifests.  Content doesn't matter because we also
    # mock away check_resources, which will consume this.
    resources = ["dummy resource"]
    krh.render_manifests = mock.MagicMock(return_value=resources)

    expected_status = BlockedStatus("a very unique status")
    krh._charm_status_given_resource_status = mock.MagicMock(return_value=expected_status)

    returned_status = krh.compute_unit_status()

    # Assert that we hit all expected helpers, and returned the expected status
    krh.render_manifests.assert_called_once()
    mocked_krh_check_resources.assert_called_once()
    assert returned_status == expected_status


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
    resource_status, errors, expected_returned_status, simple_krh_instance
):
    krh = simple_krh_instance

    returned_status = krh._charm_status_given_resource_status(
        resource_status=resource_status, errors=errors
    )

    assert returned_status == expected_returned_status


def test_KubernetesResourceHandler_render_manifests(mocker):  # noqa N802
    load_all_yaml_spy = mocker.spy(
        codecs,
        "load_all_yaml",
    )

    template_files = [
        data_dir / "template_yaml_0.j2",
        data_dir / "template_yaml_1.j2",
    ]

    context = {
        "port": 8080,
        "selector": "my-nginx",
    }

    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=template_files,
        context=context,
    )

    resource_manifest = krh.render_manifests()

    load_all_yaml_spy.assert_called_once()

    for i, r in enumerate(resource_manifest):
        assert isinstance(r, Service)
        assert r.metadata.name == f"template-{i}"
        assert r.spec.ports[0].port == context["port"]
        assert r.spec.selector["run"] == context["selector"]

    # Demonstrate that the _manifests cache works
    resource_manifest_2 = krh.render_manifests(force_recompute=False)
    # manifests returned are the same
    assert resource_manifest == resource_manifest_2
    # load_all_yaml does not get hit a second time
    load_all_yaml_spy.assert_called_once()

    # And if we provide new template_files or context, we get new manifests
    # because new inputs should clear the cache
    context_new = copy.deepcopy(context)
    context_new["port"] = 8081
    template_files_new = reversed(template_files)

    load_all_yaml_call_count = load_all_yaml_spy.call_count
    _ = krh.render_manifests(context=context_new)
    assert load_all_yaml_spy.call_count == load_all_yaml_call_count + 1

    # Reverse the yaml files to provoke a trivial
    load_all_yaml_call_count = load_all_yaml_spy.call_count
    _ = krh.render_manifests(template_files=template_files_new)
    assert load_all_yaml_spy.call_count == load_all_yaml_call_count + 1

    # setting force_recompute == True will cause us to ignore an existing cached manifest
    load_all_yaml_call_count = load_all_yaml_spy.call_count
    krh._manifests = ["some cached manifests"]
    _ = krh.render_manifests(force_recompute=True)
    assert load_all_yaml_spy.call_count == load_all_yaml_call_count + 1


def test_KubernetesResourceHandler_render_manifests_labeling(mocker):  # noqa N802
    """Tests KRH.render_manifests with labels."""
    # Arrange
    template_files = [
        data_dir / "multiple_template_yaml.j2",
    ]

    context = {}
    labels_to_add = {"new": "label", "anothernew": "label"}

    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=template_files,
        context=context,
        labels=labels_to_add,
    )

    # Act
    resource_manifest = krh.render_manifests()

    # Assert the new labels are added
    for i, r in enumerate(resource_manifest):
        for key in labels_to_add.keys():
            assert key in r.metadata.labels
            assert r.metadata.labels[key] == labels_to_add[key]

    # Assert we didn't lose the old labels
    resource_manifest[-1].metadata.labels["run"] == "my-nginx"


@pytest.mark.parametrize(
    "context,template_files,expected_raised_context",
    (
        (None, None, pytest.raises(ValueError)),  # Missing all inputs
        (None, ["template-file"], pytest.raises(ValueError)),  # Missing context
        ({"some": "context"}, None, pytest.raises(ValueError)),  # Missing template_files
        ({"some": "context"}, ["template-file"], nullcontext()),  # All inputs available
    ),
)
def test_KubernetesResourceHandler_render_manifests_missing_inputs(  # noqa: N802
    context, template_files, expected_raised_context, mocker
):  # noqa N802
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=template_files,
        context=context,
    )

    # Mock away interactions with other functions
    krh._render_manifest_parts = mock.MagicMock(return_value=[])

    expected_manifests = "some manifests"
    mocked_codecs = mocker.patch(
        "charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler.codecs"
    )
    mocked_codecs.load_all_yaml.return_value = expected_manifests

    with expected_raised_context:
        manifests = krh.render_manifests()

        krh._render_manifest_parts.assert_called_once()
        mocked_codecs.load_all_yaml.assert_called_once()
        assert manifests == expected_manifests


def test_KubernetesResourceHandler_apply(  # noqa N802
    mocker,
    simple_krh_instance,
    mocked_khr_lightkube_client_class,  # noqa F811
):
    # Dummy that will be returned from render_manifests.  Content doesn't matter because we also
    # mock away apply_many, which will consume this.
    resources = ["dummy resource"]

    krh = simple_krh_instance

    mocked_render_manifests = mock.MagicMock()
    mocked_render_manifests.return_value = resources
    krh.render_manifests = mocked_render_manifests

    mocked_apply_many = mocker.patch(
        "charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler.apply_many"
    )

    # Act
    krh.apply()

    # Assert the expected state
    mocked_render_manifests.assert_called_once()
    mocked_apply_many.assert_called_once()


@pytest.mark.parametrize(
    "resources, labels",
    (([statefulset_with_replicas], {"label1": "label1value", "label2": "label2value"}),),
)
def test_KubernetesResourceHandler_apply_with_labels(  # noqa N802
    resources,
    labels,
    mocker,
    simple_krh_instance,
    mocked_khr_lightkube_client_class,  # noqa F811
):
    """Test KRH.apply with labels."""
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=["some-file"],
        context={"some": "context"},
        labels=labels,
    )
    # Arrange
    mocked_render_manifests = mock.MagicMock()
    mocked_render_manifests.return_value = resources
    krh.render_manifests = mocked_render_manifests

    mocked_apply_many = mocker.patch(
        "charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler.apply_many"
    )

    # Act
    krh.apply()

    # Assert the labels are added
    actual_labels = mocked_apply_many.call_args_list[0].kwargs["objs"][0].metadata.labels
    for key, value in labels.items():
        assert actual_labels[key] == value


@pytest.mark.parametrize(
    "resources, resource_types, expected_raised_context",
    (
        ([statefulset_with_replicas], {Service, StatefulSet}, nullcontext()),
        ([statefulset_with_replicas], {Service}, pytest.raises(ValueError)),
    ),
)
def test_KubernetesResourceHandler_apply_with_resource_types(  # noqa N802
    resources,
    resource_types,
    expected_raised_context,
    mocker,
    simple_krh_instance,
    mocked_khr_lightkube_client_class,  # noqa F811
):
    """Test KRH.apply with resource_types."""
    # Arrange
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=["some-file"],
        context={"some": "context"},
        resource_types=resource_types,
    )

    mocked_render_manifests = mock.MagicMock()
    mocked_render_manifests.return_value = resources
    krh.render_manifests = mocked_render_manifests

    mocker.patch("charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler.apply_many")

    # Act and Assert
    with expected_raised_context:
        krh.apply()


@pytest.mark.parametrize(
    "error_raised_by_apply_many,overall_context_raised",
    (
        (None, nullcontext()),
        (FakeApiError(400), pytest.raises(FakeApiError)),
        (FakeApiError(403), pytest.raises(ErrorWithStatus)),
    ),
)
def test_KubernetesResourceHandler_apply_on_errors(  # noqa N802
    error_raised_by_apply_many,
    overall_context_raised,
    mocker,
    simple_krh_instance,
    mocked_khr_lightkube_client_class,  # noqa F811
):
    krh = simple_krh_instance

    # Dummy that will be returned from render_manifests.  Content doesn't matter because we also
    # mock away apply_many, which will consume this.
    krh.render_manifests = mock.MagicMock(return_value=[])

    mocked_apply_many = mocker.patch(
        "charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler.apply_many"
    )
    mocked_apply_many.side_effect = error_raised_by_apply_many
    with overall_context_raised:
        krh.apply()


def test_KubernetesResourceHandler_delete():  # noqa: N802
    """Tests that KRH.delete successfully deletes observed resources."""
    # Arrange
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=[],
        context={},
        labels={"some": "labels"},
        resource_types={"Some", "Types"},
    )
    krh._lightkube_client = mock.MagicMock()

    resources_to_delete = [
        Pod(metadata=ObjectMeta(name="pod1", namespace="namespace1")),
        Service(metadata=ObjectMeta(name="service1", namespace="namespace2")),
    ]
    krh.get_deployed_resources = mock.MagicMock(return_value=resources_to_delete)

    # Act
    krh.delete()

    # Assert
    assert krh._lightkube_client.delete.call_count == len(resources_to_delete)


@pytest.mark.parametrize(
    "labels, resource_types, expected_context",
    [
        (None, {"some", "resources"}, pytest.raises(ValueError)),
        ({}, {"some", "resources"}, pytest.raises(ValueError)),
        ({"some": "labels"}, None, pytest.raises(ValueError)),
        ({"some": "labels"}, {}, pytest.raises(ValueError)),
    ],
)
def test_KubernetesResourceHandler_delete_missing_required_arguments(  # noqa: N802
    labels, resource_types, expected_context
):
    """Tests that KRH delete raises when missing required inputs."""
    # Arrange
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=[],
        context={},
        labels=labels,
        resource_types=resource_types,
    )

    krh._lightkube_client = mock.MagicMock()

    # Act and Assert
    with expected_context:
        krh.get_deployed_resources()


def test_KubernetesResourceHandler_get_deployed_resources():  # noqa: N802
    """Tests that KRH.get_deployed_resources returns as expected."""
    # Arrange
    labels = {"some": "labels"}
    resource_types = {Pod, Service}

    expected_resources = [
        Pod(metadata=ObjectMeta(name="pod1", namespace="namespace1")),
        Service(metadata=ObjectMeta(name="service1", namespace="namespace2")),
    ]
    # Pack these into a nested list so we can emit them from the client.list.side_effect
    expected_resource_side_effect = [[resource] for resource in expected_resources]

    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=[],
        context={},
        labels=labels,
        resource_types=resource_types,
    )

    krh._lightkube_client = mock.MagicMock()
    krh._lightkube_client.list.side_effect = expected_resource_side_effect

    # Act
    resources = krh.get_deployed_resources()

    # Assert list called once for each resource type
    krh._lightkube_client.list.call_count == len(resource_types)

    # Assert we got the results from list
    assert resources == expected_resources


@pytest.mark.parametrize(
    "labels, resource_types, expected_context",
    [
        (None, {"some", "resources"}, pytest.raises(ValueError)),
        ({}, {"some", "resources"}, pytest.raises(ValueError)),
        ({"some": "labels"}, None, pytest.raises(ValueError)),
        ({"some": "labels"}, {}, pytest.raises(ValueError)),
    ],
)
def test_KubernetesResourceHandler_get_deployed_resources_missing_required_arguments(  # noqa: N802
    labels, resource_types, expected_context
):
    """Tests that KRH.get_deployed_resources raises when missing required inputs."""
    # Arrange
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=[],
        context={},
        labels=labels,
        resource_types=resource_types,
    )

    krh._lightkube_client = mock.MagicMock()

    # Act and Assert
    with expected_context:
        krh.get_deployed_resources()


def test_KubernetesResourceHandler_reconcile():  # noqa: N802
    """Test that KRH.reconcile works when expected to."""
    # Arrange
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=[],
        context={},
        labels={"name": "value", "name2": "value2"},
        resource_types={Pod, Service},
    )
    krh._lightkube_client = mock.MagicMock()
    krh.apply = mock.MagicMock()

    pods = codecs.load_all_yaml((data_dir / "pods_with_labels.j2").read_text())
    services = codecs.load_all_yaml((data_dir / "services_with_labels.j2").read_text())

    # Desired resources.  Excludes the last service
    krh._manifests = pods + services[:-1]

    # Existing resources.  Includes the last service
    existing_resources = pods + services
    krh.get_deployed_resources = mock.MagicMock(return_value=existing_resources)

    # Act
    krh.reconcile()

    # Assert that we tried to delete one object and then called apply
    assert krh._lightkube_client.delete.call_count == 1
    assert krh.apply.call_count == 1


@pytest.mark.parametrize(
    "labels, resource_types, expected_context",
    [
        (None, {"some", "resources"}, pytest.raises(ValueError)),
        ({}, {"some", "resources"}, pytest.raises(ValueError)),
        ({"some": "labels"}, None, pytest.raises(ValueError)),
        ({"some": "labels"}, {}, pytest.raises(ValueError)),
    ],
)
def test_KubernetesResourceHandler_reconcile_missing_required_arguments(  # noqa: N802
    labels, resource_types, expected_context
):
    """Test that KRH.reconcile raises when missing required inputs."""
    # Arrange
    krh = kubernetes.KubernetesResourceHandler(
        field_manager="field-manager",
        template_files=[],
        context={},
        labels=labels,
        resource_types=resource_types,
    )
    krh.apply = mock.MagicMock()
    krh._lightkube_client = mock.MagicMock()

    # Act and Assert
    with expected_context:
        krh.reconcile()

    krh.apply.assert_not_called()


test_namespaced_resource = create_namespaced_resource("mygroup", "myversion", "myres", "myress")
test_global_resource = create_global_resource("mygroup2", "myversion2", "myres2", "myres2s")


@pytest.mark.parametrize(
    "resource, expected",
    [
        (statefulset_with_replicas, ("apps", "v1", "StatefulSet", "has-replicas", "namespace")),
        (
            MutatingWebhookConfiguration(metadata=ObjectMeta(name="name1")),
            ("admissionregistration.k8s.io", "v1", "MutatingWebhookConfiguration", "name1", None),
        ),
        (
            test_namespaced_resource(metadata=ObjectMeta(name="name1", namespace="namespace1")),
            ("mygroup", "myversion", "myres", "name1", "namespace1"),
        ),
        (
            test_global_resource(metadata=ObjectMeta(name="name")),
            ("mygroup2", "myversion2", "myres2", "name", None),
        ),
    ],
)
def test_hash_lightkube_resource(resource, expected):
    """Tests that _hash_lightkube_resource works on a variety of resources."""
    actual = _hash_lightkube_resource(resource)
    assert actual == expected


# Helper that works like a class with an attribute
sample_classlike = NamedTuple("classlike", [("a", int)])


@pytest.mark.parametrize(
    "left, right, hasher, expected",
    [
        ([1, "two", (3, 3, 3)], ["two", (3, 3, 3), 4], None, [1]),
        (
            [sample_classlike(a=1), sample_classlike(a=2)],
            [sample_classlike(a=3), sample_classlike(a=2)],
            lambda x: x.a,
            [sample_classlike(a=1)],
        ),
        (
            [statefulset_with_replicas, statefulset_missing_replicas],
            [statefulset_missing_replicas],
            _hash_lightkube_resource,
            [statefulset_with_replicas],
        ),
        (
            [
                test_global_resource(metadata=ObjectMeta(name="name1")),
                test_global_resource(metadata=ObjectMeta(name="name2")),
            ],
            [
                test_global_resource(metadata=ObjectMeta(name="name2")),
                test_global_resource(metadata=ObjectMeta(name="name3")),
            ],
            _hash_lightkube_resource,
            [test_global_resource(metadata=ObjectMeta(name="name1"))],
        ),
    ],
)
def test_in_left_not_right(left, right, hasher, expected):
    """Tests that _in_left_not_right works on a variety of inputs."""
    actual = _in_left_not_right(left, right, hasher)
    assert actual == expected


@pytest.mark.parametrize(
    "resources, labels, expected",
    [
        ([], {}, []),
        (
            [
                Service(metadata=ObjectMeta(name="name", namespace="namespace")),
                StatefulSet(
                    metadata=ObjectMeta(
                        name="name", namespace="namespace", labels={"starting": "label"}
                    )
                ),
            ],
            {"new": "label!", "anothernew": "label!!"},
            [
                Service(
                    metadata=ObjectMeta(
                        name="name",
                        namespace="namespace",
                        labels={"new": "label!", "anothernew": "label!!"},
                    ),
                ),
                StatefulSet(
                    metadata=ObjectMeta(
                        name="name",
                        namespace="namespace",
                        labels={"starting": "label", "new": "label!", "anothernew": "label!!"},
                    )
                ),
            ],
        ),
    ],
)
def test_add_labels_to_manifest(resources, labels, expected):
    """Tests that _add_labels_to_resources works on a variety of inputs."""
    actual = _add_labels_to_resources(resources, labels)
    assert actual == expected


@pytest.mark.parametrize(
    "resources, expected_classes",
    [
        (
            [
                Service(metadata=ObjectMeta(name="name", namespace="namespace")),
                Service(metadata=ObjectMeta(name="name2", namespace="namespace")),
                StatefulSet(metadata=ObjectMeta(name="name", namespace="namespace")),
                test_global_resource(metadata=ObjectMeta(name="name")),
            ],
            {Service, StatefulSet, test_global_resource},
        ),
    ],
)
def test_get_resource_classes_in_manifests(resources, expected_classes):
    """Tests that _get_resource_classes_in_manifests works with global and namespaced resources."""
    actual_classes = _get_resource_classes_in_manifests(resources)
    assert actual_classes == expected_classes


@pytest.mark.parametrize(
    "resources, allowed_resource_types, expected_context_raised",
    [
        (
            (statefulset_with_replicas, Pod(), test_namespaced_resource()),
            (StatefulSet, Pod, test_namespaced_resource),
            nullcontext(),
        ),
        (
            (statefulset_with_replicas, Pod(), test_namespaced_resource()),
            (StatefulSet, test_namespaced_resource),
            pytest.raises(ValueError),
        ),
    ],
)
def test_validate_resources(resources, allowed_resource_types, expected_context_raised):
    """Tests that _validate_resources correctly validates the resources against an allowed list."""
    with expected_context_raised:
        _validate_resources(resources, allowed_resource_types)
