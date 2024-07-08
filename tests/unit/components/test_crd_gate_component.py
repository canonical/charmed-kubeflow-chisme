# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from unittest import mock
from ops.model import ActiveStatus, BlockedStatus

from charmed_kubeflow_chisme.components.crd_gate_component import CRDsGateComponent
from charmed_kubeflow_chisme.lightkube.mocking import FakeApiError

@pytest.fixture
def lightkube_client_mock():
    """Fixture to mock the lightkube client."""
    client = mock.MagicMock()
    yield client

@pytest.fixture
def charm_mock():
    """Fixture to mock the charm."""
    charm = mock.MagicMock()
    yield charm

def test_crd_exists(lightkube_client_mock):
    """Test that _crd_exists returns True if the CRD exists."""
    crd_name = "test-crd"
    component = CRDsGateComponent(mock.MagicMock(), "test-component", [crd_name], lightkube_client_mock)

    lightkube_client_mock.get.return_value = True
    assert component._crd_exists(crd_name) is True

def test_crd_does_not_exist(lightkube_client_mock):
    """Test that _crd_exists returns False if the CRD does not exist."""
    crd_name = "test-crd"
    component = CRDsGateComponent(mock.MagicMock(), "test-component", [crd_name], lightkube_client_mock)

    lightkube_client_mock.get.side_effect = FakeApiError(404)
    assert component._crd_exists(crd_name) is False

def test_ready_for_execution_all_crds_exist(lightkube_client_mock):
    """Test that ready_for_execution returns True if all CRDs exist."""
    crds = ["crd1", "crd2"]
    component = CRDsGateComponent(mock.MagicMock(), "test-component", crds, lightkube_client_mock)

    lightkube_client_mock.get.return_value = True
    assert component.ready_for_execution() is True

def test_ready_for_execution_some_crds_missing(lightkube_client_mock):
    """Test that ready_for_execution returns False if some CRDs are missing."""
    crds = ["crd1", "crd2"]
    component = CRDsGateComponent(mock.MagicMock(), "test-component", crds, lightkube_client_mock)

    lightkube_client_mock.get.side_effect = [True, FakeApiError(404)]
    assert component.ready_for_execution() is False

def test_get_status_all_crds_exist(lightkube_client_mock):
    """Test that get_status returns ActiveStatus if all CRDs exist."""
    crds = ["crd1", "crd2"]
    component = CRDsGateComponent(mock.MagicMock(), "test-component", crds, lightkube_client_mock)

    lightkube_client_mock.get.return_value = True
    assert isinstance(component.get_status(), ActiveStatus)

def test_get_status_some_crds_missing(lightkube_client_mock):
    """Test that get_status returns BlockedStatus if some CRDs are missing."""
    crds = ["crd1", "crd2"]
    component = CRDsGateComponent(mock.MagicMock(), "test-component", crds, lightkube_client_mock)

    lightkube_client_mock.get.side_effect = [True, FakeApiError(404)]
    status = component.get_status()
    assert isinstance(status, BlockedStatus)
    assert "Missing CRDs: crd2" in status.message
