# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import random
import string
import time
from pathlib import Path

import pytest
from lightkube import Client
from lightkube.core.exceptions import ApiError
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Namespace, Pod, Service

from charmed_kubeflow_chisme.kubernetes import (
    KubernetesResourceHandler,
    create_charm_default_labels,
)

# Note: all tests require a Kubernetes cluster to run against.

data_dir = Path(__file__).parent.joinpath("data")


def test_kubernetes_cluster_exists():
    """Test that we can connect to the Kubernetes cluster."""
    client = Client()
    client.list(Pod)


@pytest.fixture()
def namespace():
    """Creates a kubernetes namespace and yields its name, cleaning the namespace up afterwards."""
    namespace_name = f"chisme-test-namespace-{''.join(random.choices(string.digits, k=5))}"
    lightkube_client = Client()
    this_namespace = Namespace(metadata=ObjectMeta(name=namespace_name))
    lightkube_client.create(this_namespace, namespace_name)

    yield namespace_name

    try:
        lightkube_client.delete(Namespace, namespace_name)
    except ApiError as err:
        if err.code == 404:
            return
        raise err


def test_KubernetesResourceHandler_apply(namespace):  # noqa: N802
    lightkube_client = Client()
    template_files = [data_dir / "pods1.j2", data_dir / "services1.j2", data_dir / "namespace1.j2"]
    context = {"namespace": namespace}
    krh = KubernetesResourceHandler(
        "test-krh-apply",
        template_files=template_files,
        context=context,
        labels=create_charm_default_labels(application_name='my-application', model_name='my-model', scope='my-scope'),
        child_resource_types=[Pod, Service, Namespace],
    )

    # Name of the additional namespace we create during test
    additional_namespace_name = f"{namespace}-additional"

    krh.apply()

    # Assert the resources exist
    lightkube_client.get(Pod, "mypod", namespace=namespace)
    lightkube_client.get(Pod, "mypod2", namespace=namespace)
    lightkube_client.get(Service, "myservice", namespace=namespace)
    lightkube_client.get(Service, "myservice2", namespace=namespace)
    lightkube_client.get(Namespace, additional_namespace_name)

    # Reconcile away the Services by updating the template files to remove the services and
    # namespace
    krh.template_files = [data_dir / "pods1.j2"]
    krh.reconcile()

    # Give a few seconds for everything to be deleted
    time.sleep(10)

    # Assert the Pods exist but the Services do not
    lightkube_client.get(Pod, "mypod", namespace=namespace)
    lightkube_client.get(Pod, "mypod2", namespace=namespace)
    with pytest.raises(ApiError) as err:
        lightkube_client.get(Service, "myservice", namespace=namespace)
    assert err.value.status.code == 404

    with pytest.raises(ApiError) as err:
        lightkube_client.get(Service, "myservice2", namespace=namespace)
    assert err.value.status.code == 404
    with pytest.raises(ApiError) as err:
        lightkube_client.get(Namespace, additional_namespace_name)
    assert err.value.status.code == 404

    # Delete everything we created
    krh.delete()

    # Give a few seconds for everything to be deleted
    time.sleep(10)

    # Assert deleted
    with pytest.raises(ApiError) as err:
        lightkube_client.get(Pod, "mypod", namespace=namespace)
    assert err.value.status.code == 404
    with pytest.raises(ApiError) as err:
        lightkube_client.get(Pod, "mypod2", namespace=namespace)
    assert err.value.status.code == 404
