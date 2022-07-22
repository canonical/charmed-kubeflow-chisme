# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest import mock

import pytest
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apps_v1 import StatefulSet
from lightkube.resources.core_v1 import Namespace

from charmed_kubeflow_chisme.lightkube.batch import apply_many, delete_many

namespaced_resource = StatefulSet(
    metadata=ObjectMeta(name="sample-statefulset", namespace="namespace"),
)

global_resource = Namespace(
    metadata=ObjectMeta(name="sample-namespace", namespace="namespace"),
)


@pytest.mark.parametrize(
    "objects,expected_namespaces",
    (([namespaced_resource, global_resource], ["namespace", None]),),
)
def test_apply_many(
    objects, expected_namespaces, mocker, mocked_lightkube_client  # noqa F811
):  # noqa F811
    # Replace sort_objects with something that returns the objects passed, for testing
    mocked_sort_objects = mocker.patch(
        "charmed_kubeflow_chisme.lightkube.batch._many.sort_objects"
    )
    mocked_sort_objects.side_effect = lambda objs: objs

    # Other inputs passed to client.apply
    field_manager = "fm"
    force = True

    # Execute the test
    returned = apply_many(
        client=mocked_lightkube_client,
        objs=objects,
        field_manager=field_manager,
        force=force,
    )

    # We should always call sort_objects, regardless of outcome
    mocked_sort_objects.assert_called_once()

    # Inspect the operation and output
    assert len(returned) == len(objects)

    # Assert we called apply with the expected inputs
    calls = [None] * len(objects)
    for i, (obj, namespace) in enumerate(zip(objects, expected_namespaces)):
        calls[i] = mock.call(
            obj=obj, namespace=namespace, field_manager=field_manager, force=force
        )
    mocked_lightkube_client.apply.assert_has_calls(calls)


@pytest.mark.parametrize(
    "objects,context_raised",
    (
        (["something else"], pytest.raises(TypeError)),  # An iterable of bad objects
        (1, pytest.raises(TypeError)),  # Something that is not iterable
    ),
)
def test_apply_many_error(
    objects, context_raised, mocker, mocked_lightkube_client  # noqa F811
):  # noqa F811
    # Replace sort_objects with something that returns the objects passed, for testing
    mocked_sort_objects = mocker.patch(
        "charmed_kubeflow_chisme.lightkube.batch._many.sort_objects"
    )
    mocked_sort_objects.side_effect = lambda objs: objs

    # Other inputs passed to client.apply
    field_manager = "fm"
    force = True

    # Execute the test
    with context_raised:
        apply_many(
            client=mocked_lightkube_client,
            objs=objects,
            field_manager=field_manager,
            force=force,
        )

        # We should always call sort_objects, regardless of outcome
        mocked_sort_objects.assert_called_once()


@pytest.mark.parametrize(
    "objects,expected_names,expected_namespaces",
    (
        (
            [namespaced_resource, global_resource],
            ["sample-statefulset", "sample-namespace"],
            ["namespace", None],
        ),
    ),
)
def test_delete_many(
    objects,
    expected_names,
    expected_namespaces,
    mocker,
    mocked_lightkube_client,  # noqa F811
):
    # Replace sort_objects with something that returns the objects passed, for testing
    mocked_sort_objects = mocker.patch(
        "charmed_kubeflow_chisme.lightkube.batch._many.sort_objects"
    )
    mocked_sort_objects.side_effect = lambda objs, reverse: objs

    # Execute the test
    returned = delete_many(
        client=mocked_lightkube_client,
        objs=objects,
    )

    # We should always call sort_objects, regardless of outcome
    mocked_sort_objects.assert_called_once()

    # Inspect the operation and output
    assert returned is None

    # Assert we called apply with the expected inputs
    calls = [None] * len(objects)
    for i, (obj, name, namespace) in enumerate(zip(objects, expected_names, expected_namespaces)):
        calls[i] = mock.call(res=obj, name=name, namespace=namespace)
    mocked_lightkube_client.delete.assert_has_calls(calls)


@pytest.mark.parametrize(
    "objects,context_raised",
    (
        (["something else"], pytest.raises(TypeError)),  # An iterable of bad objects
        ([1], pytest.raises(TypeError)),  # Something that is not iterable
    ),
)
def test_delete_many_error(
    objects,
    context_raised,
    mocker,
    mocked_lightkube_client,  # noqa F811
):
    # Replace sort_objects with something that returns the objects passed, for testing
    mocked_sort_objects = mocker.patch(
        "charmed_kubeflow_chisme.lightkube.batch._many.sort_objects"
    )
    mocked_sort_objects.side_effect = lambda objs, reverse: objs

    # Execute the test
    with context_raised:
        delete_many(
            client=mocked_lightkube_client,
            objs=objects,
        )

        # We should always call sort_objects, regardless of outcome
        mocked_sort_objects.assert_called_once()
