# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import AsyncMock, Mock, patch

import lightkube
import pytest
from juju.application import Application
from juju.model import Model

from charmed_kubeflow_chisme.testing.ambient_integration import (
    ISTIO_BEACON_K8S_APP,
    ISTIO_INGRESS_K8S_APP,
    ISTIO_K8S_APP,
    assert_path_reachable_through_ingress,
    deploy_and_integrate_service_mesh_charms,
    fetch_response,
    integrate_with_service_mesh,
)


@pytest.mark.asyncio
async def test_deploy_and_integrate_service_mesh_charms_app_not_found():
    """Test deploy service mesh charms with non-existing app."""
    app_name = "my-app"
    model = AsyncMock(spec_set=Model)
    model.applications = {}
    model.name = "test-model"

    with pytest.raises(AssertionError, match=f"application {app_name} was not found"):
        await deploy_and_integrate_service_mesh_charms(app_name, model)


@pytest.mark.asyncio
async def test_deploy_and_integrate_service_mesh_charms():
    """Test deploy and integrate Istio service mesh charms."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await deploy_and_integrate_service_mesh_charms(app_name, model, channel="2/stable")

    # Verify all three Istio charms were deployed
    assert model.deploy.call_count == 3
    model.deploy.assert_any_await(ISTIO_K8S_APP, channel="2/stable", trust=True)
    model.deploy.assert_any_await(ISTIO_INGRESS_K8S_APP, channel="2/stable", trust=True)
    model.deploy.assert_any_await(ISTIO_BEACON_K8S_APP, channel="2/stable", trust=True)

    # Verify integrations
    assert model.integrate.call_count == 2
    model.integrate.assert_any_await(
        f"{ISTIO_INGRESS_K8S_APP}:istio-ingress-route", f"{app_name}:istio-ingress-route"
    )
    model.integrate.assert_any_await(
        f"{ISTIO_BEACON_K8S_APP}:service-mesh", f"{app_name}:service-mesh"
    )

    # Verify wait for idle
    model.wait_for_idle.assert_awaited_once_with(
        raise_on_blocked=False,
        raise_on_error=True,
        timeout=900,
    )


@pytest.mark.asyncio
async def test_deploy_and_integrate_service_mesh_charms_default_channel():
    """Test deploy service mesh charms with default channel."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await deploy_and_integrate_service_mesh_charms(app_name, model)

    # Verify default channel is used
    model.deploy.assert_any_await(ISTIO_K8S_APP, channel="2/edge", trust=True)


@pytest.mark.asyncio
async def test_deploy_and_integrate_service_mesh_charms_no_ingress():
    """Test deploy service mesh charms without ingress integration."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await deploy_and_integrate_service_mesh_charms(app_name, model, relate_to_ingress=False)

    # Verify all three Istio charms were deployed
    assert model.deploy.call_count == 3

    # Verify only beacon integration (no ingress)
    assert model.integrate.call_count == 1
    model.integrate.assert_any_await(
        f"{ISTIO_BEACON_K8S_APP}:service-mesh", f"{app_name}:service-mesh"
    )


@pytest.mark.asyncio
async def test_deploy_and_integrate_service_mesh_charms_no_beacon():
    """Test deploy service mesh charms without beacon integration."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await deploy_and_integrate_service_mesh_charms(app_name, model, relate_to_beacon=False)

    # Verify all three Istio charms were deployed
    assert model.deploy.call_count == 3

    # Verify only ingress integration (no beacon)
    assert model.integrate.call_count == 1
    model.integrate.assert_any_await(
        f"{ISTIO_INGRESS_K8S_APP}:istio-ingress-route", f"{app_name}:istio-ingress-route"
    )


@pytest.mark.asyncio
async def test_deploy_and_integrate_service_mesh_charms_no_integrations():
    """Test deploy service mesh charms without any integrations."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await deploy_and_integrate_service_mesh_charms(
        app_name, model, relate_to_ingress=False, relate_to_beacon=False
    )

    # Verify all three Istio charms were deployed
    assert model.deploy.call_count == 3

    # Verify no integrations
    model.integrate.assert_not_called()

    # Still waits for idle
    model.wait_for_idle.assert_awaited_once()


@pytest.mark.asyncio
async def test_integrate_with_service_mesh_app_not_found():
    """Test integrate with service mesh with non-existing app."""
    app_name = "my-app"
    model = AsyncMock(spec_set=Model)
    model.applications = {}
    model.name = "test-model"

    with pytest.raises(AssertionError, match=f"application {app_name} was not found"):
        await integrate_with_service_mesh(app_name, model)


@pytest.mark.asyncio
async def test_integrate_with_service_mesh():
    """Test integrate existing app with service mesh charms."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await integrate_with_service_mesh(app_name, model)

    # Verify integrations only (no deploys)
    model.deploy.assert_not_called()

    assert model.integrate.call_count == 2
    model.integrate.assert_any_await(
        f"{ISTIO_INGRESS_K8S_APP}:istio-ingress-route", f"{app_name}:istio-ingress-route"
    )
    model.integrate.assert_any_await(
        f"{ISTIO_BEACON_K8S_APP}:service-mesh", f"{app_name}:service-mesh"
    )

    # Verify wait for idle
    model.wait_for_idle.assert_awaited_once_with(
        raise_on_blocked=False,
        raise_on_error=True,
        timeout=900,
    )


@pytest.mark.asyncio
async def test_integrate_with_service_mesh_no_ingress():
    """Test integrate with service mesh without ingress integration."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await integrate_with_service_mesh(app_name, model, relate_to_ingress=False)

    # Verify only beacon integration
    assert model.integrate.call_count == 1
    model.integrate.assert_any_await(
        f"{ISTIO_BEACON_K8S_APP}:service-mesh", f"{app_name}:service-mesh"
    )


@pytest.mark.asyncio
async def test_integrate_with_service_mesh_no_beacon():
    """Test integrate with service mesh without beacon integration."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await integrate_with_service_mesh(app_name, model, relate_to_beacon=False)

    # Verify only ingress integration
    assert model.integrate.call_count == 1
    model.integrate.assert_any_await(
        f"{ISTIO_INGRESS_K8S_APP}:istio-ingress-route", f"{app_name}:istio-ingress-route"
    )


@pytest.mark.asyncio
async def test_integrate_with_service_mesh_no_integrations():
    """Test integrate with service mesh with no integrations enabled."""
    app_name = "my-app"
    app = Mock(spec_set=Application)()
    app.name = app_name

    model = AsyncMock(spec_set=Model)
    model.applications = {app_name: app}
    model.name = "test-model"

    await integrate_with_service_mesh(
        app_name, model, relate_to_ingress=False, relate_to_beacon=False
    )

    # Verify no integrations
    model.integrate.assert_not_called()

    # Still waits for idle
    model.wait_for_idle.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_response():
    """Test fetch_response returns status, text, and content type."""
    url = "http://example.com/test"
    headers = {"Authorization": "Bearer token"}

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<html>Test</html>")
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.get = Mock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        status, text, content_type = await fetch_response(url, headers)

    assert status == 200
    assert text == "<html>Test</html>"
    assert content_type == "text/html"
    mock_session.get.assert_called_once_with(url, headers=headers)


@pytest.mark.asyncio
async def test_fetch_response_strips_charset():
    """Test fetch_response strips charset from content type."""
    url = "http://example.com/api"

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='{"key": "value"}')
    mock_response.headers = {"Content-Type": "application/json; charset=UTF-8"}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.get = Mock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        status, text, content_type = await fetch_response(url)

    assert content_type == "application/json"


@pytest.mark.asyncio
async def test_fetch_response_no_content_type():
    """Test fetch_response handles missing Content-Type header."""
    url = "http://example.com/test"

    mock_response = AsyncMock()
    mock_response.status = 204
    mock_response.text = AsyncMock(return_value="")
    mock_response.headers = {}
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.get = Mock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        status, text, content_type = await fetch_response(url)

    assert status == 204
    assert content_type == ""


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress(mock_fetch_response, mock_lightkube_client):
    """Test assert path is reachable through ingress."""
    namespace = "test-namespace"
    http_path = "/test-path"
    external_ip = "10.0.0.1"

    # Mock lightkube client
    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    # Mock service with LoadBalancer IP
    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    # Mock fetch_response
    mock_fetch_response.return_value = (200, "<html>Success</html>", "text/html")

    await assert_path_reachable_through_ingress(http_path, namespace)

    # Verify lightkube client calls
    mock_client_instance.get.assert_called_once_with(
        lightkube.resources.core_v1.Service,
        name="istio-ingress-k8s-istio",
        namespace=namespace,
    )

    # Verify fetch_response was called with correct URL
    expected_url = f"http://{external_ip}{http_path}"
    mock_fetch_response.assert_awaited_once_with(expected_url, None)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_with_custom_service(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path reachable with custom service name."""
    namespace = "test-namespace"
    http_path = "/api"
    service_name = "custom-ingress-service"
    external_ip = "192.168.1.1"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    mock_fetch_response.return_value = (200, "OK", "text/plain")

    await assert_path_reachable_through_ingress(http_path, namespace, service_name=service_name)

    mock_client_instance.get.assert_called_once_with(
        lightkube.resources.core_v1.Service,
        name=service_name,
        namespace=namespace,
    )


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
async def test_assert_path_reachable_through_ingress_no_loadbalancer_ip(mock_lightkube_client):
    """Test assert path fails when LoadBalancer IP is not available."""
    namespace = "test-namespace"
    http_path = "/test"
    service_name = "istio-ingress-k8s-istio"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    # Mock service without LoadBalancer IP
    mock_service = Mock()
    mock_service.status.loadBalancer.ingress = []
    mock_client_instance.get.return_value = mock_service

    with pytest.raises(
        AssertionError,
        match=f"Service {service_name} in namespace {namespace} does not have a LoadBalancer IP",
    ):
        await assert_path_reachable_through_ingress(http_path, namespace)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_wrong_status(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path fails when status code doesn't match."""
    namespace = "test-namespace"
    http_path = "/test"
    external_ip = "10.0.0.1"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    # Return 404 instead of expected 200
    mock_fetch_response.return_value = (404, "Not Found", "text/html")

    with pytest.raises(AssertionError, match="Expected status 200 but got 404"):
        await assert_path_reachable_through_ingress(http_path, namespace, expected_status=200)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_with_headers(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path with custom headers."""
    namespace = "test-namespace"
    http_path = "/api"
    headers = {"Authorization": "Bearer token", "X-Custom": "value"}
    external_ip = "10.0.0.1"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    mock_fetch_response.return_value = (200, "OK", "text/plain")

    await assert_path_reachable_through_ingress(http_path, namespace, headers=headers)

    expected_url = f"http://{external_ip}{http_path}"
    mock_fetch_response.assert_awaited_once_with(expected_url, headers)


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_check_content_type(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path checks content type when provided."""
    namespace = "test-namespace"
    http_path = "/api"
    external_ip = "10.0.0.1"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    mock_fetch_response.return_value = (200, '{"data": "value"}', "application/json")

    await assert_path_reachable_through_ingress(
        http_path, namespace, expected_content_type="application/json"
    )


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_wrong_content_type(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path fails when content type doesn't match."""
    namespace = "test-namespace"
    http_path = "/api"
    external_ip = "10.0.0.1"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    mock_fetch_response.return_value = (200, "<html>Page</html>", "text/html")

    with pytest.raises(
        AssertionError,
        match="Expected content type 'application/json' but got 'text/html'",
    ):
        await assert_path_reachable_through_ingress(
            http_path, namespace, expected_content_type="application/json"
        )


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_check_response_text(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path checks response text when provided."""
    namespace = "test-namespace"
    http_path = "/test"
    external_ip = "10.0.0.1"
    expected_text = "Welcome"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    mock_fetch_response.return_value = (200, "<html>Welcome to our site</html>", "text/html")

    await assert_path_reachable_through_ingress(
        http_path, namespace, expected_response_text=expected_text
    )


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_response_text_not_found(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path fails when expected text is not in response."""
    namespace = "test-namespace"
    http_path = "/test"
    external_ip = "10.0.0.1"
    expected_text = "Dashboard"

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    mock_fetch_response.return_value = (200, "<html>Welcome Page</html>", "text/html")

    with pytest.raises(
        AssertionError,
        match=f"Expected response text to contain '{expected_text}'",
    ):
        await assert_path_reachable_through_ingress(
            http_path, namespace, expected_response_text=expected_text
        )


@pytest.mark.asyncio
@patch("charmed_kubeflow_chisme.testing.ambient_integration.lightkube.Client")
@patch("charmed_kubeflow_chisme.testing.ambient_integration.fetch_response")
async def test_assert_path_reachable_through_ingress_all_checks(
    mock_fetch_response, mock_lightkube_client
):
    """Test assert path with all validation parameters."""
    namespace = "kubeflow"
    http_path = "/volumes/"
    external_ip = "10.0.0.1"
    headers = {"kubeflow-userid": "user@example.com"}

    mock_client_instance = Mock()
    mock_lightkube_client.return_value = mock_client_instance

    mock_service = Mock()
    mock_ingress = Mock()
    mock_ingress.ip = external_ip
    mock_service.status.loadBalancer.ingress = [mock_ingress]
    mock_client_instance.get.return_value = mock_service

    response_text = (
        "<html><head><title>Volumes</title></head><body>Manage your volumes</body></html>"
    )
    mock_fetch_response.return_value = (200, response_text, "text/html")

    await assert_path_reachable_through_ingress(
        http_path,
        namespace,
        headers=headers,
        expected_status=200,
        expected_content_type="text/html",
        expected_response_text="Volumes",
    )

    # All checks should pass without raising
    expected_url = f"http://{external_ip}{http_path}"
    mock_fetch_response.assert_awaited_once_with(expected_url, headers)
