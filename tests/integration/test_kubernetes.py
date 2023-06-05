# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import random
import string
from pathlib import Path

import pytest
import tenacity
from lightkube import Client
from lightkube.core.exceptions import ApiError
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Namespace, Pod, Service

from charmed_kubeflow_chisme.kubernetes import (
    KubernetesResourceHandler,
    create_charm_default_labels,
)

# Note: all tests require a Kubernetes cluster to run against.

logger = logging.getLogger(__name__)
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
    """Tests that the KRH.apply works when expected."""
    lightkube_client = Client()
    template_files = [data_dir / "pods1.j2", data_dir / "services1.j2", data_dir / "namespace1.j2"]
    context = {"namespace": namespace}
    krh = KubernetesResourceHandler(
        "test-krh-apply",
        template_files=template_files,
        context=context,
        labels=create_charm_default_labels(
            application_name="my-application", model_name="my-model", scope="my-scope"
        ),
        resource_types={Pod, Service, Namespace},
    )

    # Name of the additional namespace we create during test
    additional_namespace_name = f"{namespace}-additional"

    krh.apply()

    # Assert the resources exist
    assert_resource_exists(
        lightkube_client=lightkube_client,
        resource_type=Pod,
        resource_name="mypod",
        resource_namespace=namespace,
    )
    assert_resource_exists(
        lightkube_client=lightkube_client,
        resource_type=Pod,
        resource_name="mypod2",
        resource_namespace=namespace,
    )
    assert_resource_exists(
        lightkube_client=lightkube_client,
        resource_type=Service,
        resource_name="myservice",
        resource_namespace=namespace,
    )
    assert_resource_exists(
        lightkube_client=lightkube_client,
        resource_type=Service,
        resource_name="myservice2",
        resource_namespace=namespace,
    )
    assert_resource_exists(
        lightkube_client=lightkube_client,
        resource_type=Namespace,
        resource_name=additional_namespace_name,
        resource_namespace=None,
    )

    # Reconcile away the Services by updating the template files to remove the services and
    # namespace
    krh.template_files = [data_dir / "pods1.j2"]
    krh.reconcile()

    # Assert the Pods exist but the Services do not
    assert_resource_exists(
        lightkube_client=lightkube_client,
        resource_type=Pod,
        resource_name="mypod",
        resource_namespace=namespace,
    )
    assert_resource_exists(
        lightkube_client=lightkube_client,
        resource_type=Pod,
        resource_name="mypod2",
        resource_namespace=namespace,
    )
    assert_resource_does_not_exist(
        lightkube_client=lightkube_client,
        resource_type=Service,
        resource_name="myservice",
        resource_namespace=namespace,
    )
    assert_resource_does_not_exist(
        lightkube_client=lightkube_client,
        resource_type=Service,
        resource_name="myservice2",
        resource_namespace=namespace,
    )
    assert_resource_does_not_exist(
        lightkube_client=lightkube_client,
        resource_type=Namespace,
        resource_name=additional_namespace_name,
        resource_namespace=None,
    )

    # Delete everything we created
    krh.delete()

    # Assert deleted
    assert_resource_does_not_exist(
        lightkube_client=lightkube_client,
        resource_type=Pod,
        resource_name="mypod",
        resource_namespace=namespace,
    )
    assert_resource_does_not_exist(
        lightkube_client=lightkube_client,
        resource_type=Pod,
        resource_name="mypod2",
        resource_namespace=namespace,
    )


@tenacity.retry(
    stop=tenacity.stop_after_delay(60),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def assert_resource_exists(lightkube_client, resource_type, resource_name, resource_namespace):
    """Raises if the given resource exists."""
    logger.info(
        f"Checking if {resource_type} {resource_name} exists in namespace {resource_namespace}"
    )
    try:
        lightkube_client.get(resource_type, resource_name, namespace=resource_namespace)
    except Exception:
        raise AssertionError(
            f"Resource {resource_type} {resource_name} in namespace {resource_namespace} does not exist when it should"
        )


@tenacity.retry(
    stop=tenacity.stop_after_delay(60),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def assert_resource_does_not_exist(
    lightkube_client, resource_type, resource_name, resource_namespace
):
    """Raises if the given resource does not exist."""
    logger.info(
        f"Checking if {resource_type} {resource_name} does not exist in namespace {resource_namespace}"
    )
    try:
        lightkube_client.get(resource_type, resource_name, namespace=resource_namespace)
        raise AssertionError(
            f"Resource {resource_type} {resource_name} in namespace {resource_namespace} exists when should not"
        )
    except ApiError as err:
        # Resource does not exist, which is what we want
        if err.status.code == 404:
            return
        raise err
