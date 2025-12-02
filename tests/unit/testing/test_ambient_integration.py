# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import AsyncMock, Mock, patch

import lightkube
import pytest
from juju.application import Application
from juju.model import Model

from charmed_kubeflow_chisme.testing.ambient_integration import (
    assert_path_reachable_through_ingress,
    deploy_and_integrate_service_mesh_charms,
    get_http_response,
    integrate_with_service_mesh,
)

ISTIO_K8S_APP = "istio-k8s"
ISTIO_INGRESS_K8S_APP = "istio-ingress-k8s"
ISTIO_BEACON_K8S_APP = "istio-beacon-k8s"
ISTIO_INGRESS_ROUTE_ENDPOINT = "istio-ingress-route"
SERVICE_MESH_ENDPOINT = "service-mesh"


@pytest.mark.asyncio
async def test_deploy_and_integrate_service_mesh_charms():
    """Test deploy and integrate service mesh charms with various parameters."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    # Test with custom channel and selective integration
    await deploy_and_integrate_service_mesh_charms(
        app_name, model, channel="2/stable", relate_to_ingress=False, relate_to_beacon=True
    )

    # Verify all three Istio charms were deployed with custom channel
    assert model.deploy.call_count == 3
    model.deploy.assert_any_await(ISTIO_K8S_APP, channel="2/stable", trust=True)
    model.deploy.assert_any_await(ISTIO_INGRESS_K8S_APP, channel="2/stable", trust=True)
    model.deploy.assert_any_await(ISTIO_BEACON_K8S_APP, channel="2/stable", trust=True)

    # Verify only beacon integration (covers relate_to_beacon=True, relate_to_ingress=False)
    assert model.integrate.call_count == 1
    model.integrate.assert_any_await(
        f"{ISTIO_BEACON_K8S_APP}:{SERVICE_MESH_ENDPOINT}", f"{app_name}:{SERVICE_MESH_ENDPOINT}"
    )

    # Verify wait for idle
    model.wait_for_idle.assert_awaited_once()


@pytest.mark.asyncio
async def test_integrate_with_service_mesh():
    """Test integrate with service mesh with both relations."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    # Test with only ingress enabled
    await integrate_with_service_mesh(
        app_name, model, relate_to_ingress=True, relate_to_beacon=False
    )

    # Verify no deploys
    model.deploy.assert_not_called()

    # Verify only ingress integration (covers relate_to_ingress=True, relate_to_beacon=False)
    assert model.integrate.call_count == 1
    model.integrate.assert_any_await(
        f"{ISTIO_INGRESS_K8S_APP}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
        f"{app_name}:{ISTIO_INGRESS_ROUTE_ENDPOINT}",
    )

    model.wait_for_idle.assert_awaited_once()


@pytest.mark.asyncio
async def test_integrate_with_service_mesh_app_not_found():
    """Test integrate with service mesh raises AssertionError when app is not found."""
    app_name = "my-app"
    model = AsyncMock(spec_set=Model)
    model.applications = {}
    model.name = "test-model"

    with pytest.raises(AssertionError, match=f"application {app_name} was not found"):
        await integrate_with_service_mesh(app_name, model)


@pytest.mark.asyncio
async def test_integrate_with_service_mesh_no_integrations(caplog):
    """Test integrate with service mesh logs warning when both relate options are False."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    # Test with both relate options disabled
    await integrate_with_service_mesh(
        app_name, model, relate_to_ingress=False, relate_to_beacon=False
    )

    # Verify warning was logged
    assert "No integrations requested" in caplog.text
    assert "Skipping integration" in caplog.text

    # Verify no integrations or wait_for_idle were called
    model.deploy.assert_not_called()
    model.integrate.assert_not_called()
    model.wait_for_idle.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers,response_headers,expected_status,expected_text,expected_content_type",
    [
        (
            {"Authorization": "Bearer token"},
            {"Content-Type": "text/html; charset=utf-8"},
            200,
            "<html>Test</html>",
            "text/html",
        ),
        (None, {}, 204, "", ""),
    ],
    ids=["with_content_type", "no_content_type"],
)
async def test_get_http_response(
    headers, response_headers, expected_status, expected_text, expected_content_type
):
    """Test get_http_response performs GET request and handles various response scenarios."""
    url = "http://example.com/test"

    mock_response = AsyncMock()
    mock_response.status = expected_status
    mock_response.text = AsyncMock(return_value=expected_text)
    mock_response.headers = response_headers
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.get = Mock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        status, text, content_type = await get_http_response(url, headers)

    assert status == expected_status
    assert text == expected_text
    assert content_type == expected_content_type
    mock_session.get.assert_called_once_with(url, headers=headers)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.get_http_response")
@pytest.mark.parametrize(
    "has_ip,service_name,headers,response,expected_status,expected_content_type,"
    "expected_response_text,should_raise,error_match",
    [
        # Successful validation with all features
        (
            True,
            "custom-service",
            {"Authorization": "Bearer token"},
            (200, "<html>Success</html>", "text/html"),
            200,
            "text/html",
            "Success",
            False,
            None,
        ),
        # No LoadBalancer IP
        (
            False,
            "istio-ingress-k8s-istio",
            None,
            None,
            None,
            None,
            None,
            True,
            "does not have a LoadBalancer IP",
        ),
        # Wrong status code
        (
            True,
            "istio-ingress-k8s-istio",
            None,
            (404, "Not Found", "text/html"),
            200,
            None,
            None,
            True,
            "Expected status 200 but got 404",
        ),
        # Wrong content type
        (
            True,
            "istio-ingress-k8s-istio",
            None,
            (200, "<html>Page</html>", "text/html"),
            None,
            "application/json",
            None,
            True,
            "Expected content type 'application/json' but got 'text/html'",
        ),
        # Missing expected text in response
        (
            True,
            "istio-ingress-k8s-istio",
            None,
            (200, "<html>Welcome Page</html>", "text/html"),
            None,
            None,
            "Dashboard",
            True,
            "Expected response text to contain 'Dashboard'",
        ),
    ],
    ids=[
        "success_with_all_features",
        "no_loadbalancer_ip",
        "wrong_status",
        "wrong_content_type",
        "missing_response_text",
    ],
)
async def test_assert_path_reachable_through_ingress(
    mock_get_response,
    mock_lightkube_client,
    has_ip,
    service_name,
    headers,
    response,
    expected_status,
    expected_content_type,
    expected_response_text,
    should_raise,
    error_match,
):
    """Test assert path reachable through ingress with various scenarios."""
    namespace = "test-namespace"
    http_path = "/test-path" if service_name == "custom-service" else "/test"
    external_ip = "10.0.0.1"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    if has_ip:
        mock_ingress = Mock()
        mock_ingress.ip = external_ip
        mock_service.status.loadBalancer.ingress = [mock_ingress]
        if response:
            mock_get_response.return_value = response
    else:
        mock_service.status.loadBalancer.ingress = []

    mock_client_instance.get.return_value = mock_service

    kwargs = {"service_name": service_name} if service_name != "istio-ingress-k8s-istio" else {}
    if headers:
        kwargs["headers"] = headers
    if expected_status:
        kwargs["expected_status"] = expected_status
    if expected_content_type:
        kwargs["expected_content_type"] = expected_content_type
    if expected_response_text:
        kwargs["expected_response_text"] = expected_response_text

    if should_raise:
        with pytest.raises(AssertionError, match=error_match):
            await assert_path_reachable_through_ingress(http_path, namespace, **kwargs)
    else:
        await assert_path_reachable_through_ingress(http_path, namespace, **kwargs)

        # Verify lightkube client calls with custom service name
        mock_client_instance.get.assert_called_once_with(
            lightkube.resources.core_v1.Service,
            name=service_name,
            namespace=namespace,
        )

        # Verify get_http_response was called with correct URL and headers
        expected_url = f"http://{external_ip}{http_path}"
        mock_get_response.assert_awaited_once_with(expected_url, headers)
