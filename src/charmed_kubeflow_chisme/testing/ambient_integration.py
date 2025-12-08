# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helpers for testing Istio ambient mode service mesh integration."""

import logging

import aiohttp
import lightkube
from juju.model import Model

logger = logging.getLogger(__name__)

ISTIO_K8S_APP = "istio-k8s"
ISTIO_INGRESS_K8S_APP = "istio-ingress-k8s"
ISTIO_BEACON_K8S_APP = "istio-beacon-k8s"
ISTIO_INGRESS_ROUTE_ENDPOINT = "istio-ingress-route"
SERVICE_MESH_ENDPOINT = "service-mesh"


async def deploy_and_integrate_service_mesh_charms(
    app: str,
    model: Model,
    channel: str = "2/edge",
    relate_to_ingress: bool = True,
    relate_to_beacon: bool = True,
    model_on_mesh: bool = True,
) -> None:
    """Deploy Istio service mesh charms (ambient mode).

    Deploy Istio service mesh charms in the given model, relate them to the given app,
    and wait for the model to become idle.

    Args:
        app: The name of the application to relate the Istio charms to.
        model: The Juju model where the charms will be deployed.
        channel: The channel from which to deploy the Istio charms. Defaults to "2/edge".
        relate_to_ingress: Whether to integrate with the istio-ingress charm. Defaults to True.
        relate_to_beacon: Whether to integrate with the istio-beacon charm. Defaults to True.
        model_on_mesh: Whether the model should be included in the mesh. Defaults to True.
    """
    await model.deploy(
        ISTIO_K8S_APP,
        channel=channel,
        trust=True,
    )

    await model.deploy(
        ISTIO_INGRESS_K8S_APP,
        channel=channel,
        trust=True,
    )

    await model.deploy(
        ISTIO_BEACON_K8S_APP,
        channel=channel,
        trust=True,
        config={"model-on-mesh": model_on_mesh},
    )

    await integrate_with_service_mesh(
        app=app,
        model=model,
        relate_to_ingress=relate_to_ingress,
        relate_to_beacon=relate_to_beacon,
    )


async def integrate_with_service_mesh(
    app: str,
    model: Model,
    relate_to_ingress: bool = True,
    relate_to_beacon: bool = True,
) -> None:
    """Integrate the application with Istio service mesh charms.

    Integrate the given application with the Istio service mesh charms in the given model.

    Args:
        app: The name of the application to relate the Istio charms to.
        model: The Juju model where the charms are deployed.
        relate_to_ingress: Whether to integrate with the istio-ingress charm. Defaults to True.
        relate_to_beacon: Whether to integrate with the istio-beacon charm. Defaults to True.
    """
    if not relate_to_ingress and not relate_to_beacon:
        logger.warning(
            "No integrations requested (both relate_to_ingress and relate_to_beacon are False). "
            "Skipping integration."
        )
        return

    assert app in model.applications, f"application {app} was not found in model {model.name}"

    if relate_to_ingress:
        await model.integrate(
            f"{ISTIO_INGRESS_K8S_APP}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
            f"{app}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
        )

    if relate_to_beacon:
        await model.integrate(
            f"{ISTIO_BEACON_K8S_APP}:{SERVICE_MESH_ENDPOINT}",
            f"{app}:{SERVICE_MESH_ENDPOINT}",
        )

    await model.wait_for_idle(
        [ISTIO_BEACON_K8S_APP, ISTIO_INGRESS_K8S_APP, ISTIO_K8S_APP],
        raise_on_blocked=False,
        raise_on_error=False,
        wait_for_active=True,
        timeout=900,
    )

    await model.wait_for_idle(
        [app],
        raise_on_blocked=False,
        raise_on_error=True,
        wait_for_active=True,
        timeout=900,
    )


async def get_http_response(url: str, headers: dict | None = None) -> tuple[int, str, str]:
    """Perform HTTP GET request and return status, text, and content-type.

    Sends an HTTP GET request to the provided URL and returns a tuple containing
    the status code, response text, and content-type (media type only).

    Args:
        url: The URL to send the GET request to.
        headers: Optional HTTP headers to include in the request.

    Returns:
        A tuple of (status_code, response_text, content_type).
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            result_status = response.status
            result_text = await response.text()
            # Extract only the media type, removing charset and other parameters
            full_content_type = response.headers.get("Content-Type", "")
            content_type = full_content_type.split(";")[0].strip()
    return result_status, result_text, content_type


async def assert_path_reachable_through_ingress(
    http_path: str,
    namespace: str,
    service_name: str = "istio-ingress-k8s-istio",
    headers: dict | None = None,
    expected_status: int = 200,
    expected_content_type: str | None = None,
    expected_response_text: str | None = None,
) -> None:
    """Assert that a given path is reachable through the Istio ingress gateway.

    Args:
        http_path: The HTTP path to test.
        namespace: The Kubernetes namespace where the Istio ingress gateway is deployed.
        service_name: The name of the Istio ingress gateway service.
            Defaults to "istio-ingress-k8s-istio".
        headers: Optional HTTP headers to include in the request. Defaults to None.
        expected_status: The expected HTTP status code. Defaults to 200.
        expected_content_type: Optional content type to check in the response headers.
            Media type only, e.g., "text/html".
        expected_response_text: Optional text that should be contained in the response body.
    """
    # Get the external IP of the Istio ingress gateway service
    client = lightkube.Client()

    gateway_svc = client.get(
        lightkube.resources.core_v1.Service,
        name=service_name,
        namespace=namespace,
    )

    # Check if LoadBalancer ingress is available
    assert (
        gateway_svc.status.loadBalancer.ingress
    ), f"Service {service_name} in namespace {namespace} does not have a LoadBalancer IP"

    external_ip = gateway_svc.status.loadBalancer.ingress[0].ip

    # Fetch the response from the ingress gateway
    url = f"http://{external_ip}{http_path}"
    response_status, response_text, response_content_type = await get_http_response(url, headers)

    # Check if the response status matches the expected status
    assert response_status == expected_status, (
        f"Expected status {expected_status} but got {response_status} " f"when accessing {url}"
    )

    # Optionally check if the content type matches the expected content type
    if expected_content_type is not None:
        assert (
            expected_content_type == response_content_type
        ), f"Expected content type '{expected_content_type}' but got '{response_content_type}' in response from {url}"

    # Optionally check if the response text matches the expected response text
    if expected_response_text is not None:
        assert expected_response_text in response_text, (
            f"Expected response text to contain '{expected_response_text}' "
            f"but it was not found in response from {url}"
        )
