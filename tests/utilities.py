# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest import mock

import pytest


@pytest.fixture()
def mocked_lightkube_client_class(mocker):
    """Prevents lightkube clients from being created, returning a mock instead"""
    mocked_lightkube_client_class = mocker.patch("lightkube.Client")
    mocked_lightkube_client_class.return_value = mock.MagicMock()
    yield mocked_lightkube_client_class


@pytest.fixture()
def mocked_lightkube_client(mocked_lightkube_client_class):
    """Prevents lightkube clients from being created, returning a mock instead"""
    yield mocked_lightkube_client_class()

