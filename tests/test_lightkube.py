# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
from contextlib import nullcontext
from unittest import mock

from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.apps_v1 import StatefulSet
from lightkube.resources.core_v1 import Namespace
import pytest

from k8s_resource_handler.lightkube.batch import apply_many
from utilities import mocked_lightkube_client_class, mocked_lightkube_client  # Imports a fixture # noqa 401


namespaced_resource = StatefulSet(
    metadata=ObjectMeta(name="has-replicas", namespace="namespace"),
)

global_resource = Namespace(
    metadata=ObjectMeta(name="has-replicas", namespace="namespace"),
)

@pytest.mark.parametrize(
    "objects,expected_namespaces,context_raised",
    (
        ([namespaced_resource, global_resource], ["namespace", None], nullcontext()),
        (["something else"], None, pytest.raises(TypeError)),
    )
)
def test_apply_many(objects, expected_namespaces, context_raised, mocker, mocked_lightkube_client):

    mocked_sort_objects = mocker.patch("k8s_resource_handler.lightkube.batch._many.sort_objects")
    # Mocked sort_objects just passes the objects back to the called for testing
    mocked_sort_objects.side_effect = lambda x: x

    field_manager = "fm"
    force = True

    with context_raised as error_info:
        returned = apply_many(
            client=mocked_lightkube_client,
            objs=objects,
            field_manager=field_manager,
            force=force,
        )

        # asser on mocked_lightkube_client.apply
        mocked_sort_objects.assert_called_once()

        if error_info is not None:
            # Error raised - this will be handled by the "with context_raised"
            pass
        else:
            # No error raised, so inspect the operation and output
            calls = [None] * len(objects)
            for i, (obj, namespace) in enumerate(zip(objects, expected_namespaces)):
                calls[i] = mock.call(
                    obj=obj, namespace=namespace, field_manager=field_manager, force=force
                )

            mocked_lightkube_client.apply.assert_has_calls(calls)
            assert len(returned) == len(objects)
