# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest import mock

import pytest
from ops.pebble import ChangeError, Layer, Plan

from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from charmed_kubeflow_chisme.pebble import update_layer


@pytest.fixture()
def mocked_container(mocker):
    mocked_container = mocker.patch("ops.model.Container")
    mocked_container.return_value = mock.MagicMock()
    yield mocked_container


@pytest.fixture()
def mocked_logger(mocker):
    mocked_logger = mocker.patch("logging.Logger")
    yield mocked_logger


def test_layer_replanned(mocked_container, mocked_logger):
    container_name = "test-container"
    mocked_container.get_plan.return_value = Plan(
        str({"services": {container_name: {"summary": "original plan"}}})
    )

    new_layer = Layer({"services": {container_name: {"summary": "new plan"}}})

    update_layer(container_name, mocked_container, new_layer, mocked_logger)

    mocked_container.get_plan.assert_called_once()
    mocked_container.replan.assert_called_once()


def test_layer_unchanged(mocked_container, mocked_logger):
    container_name = "test-container"
    mocked_container.get_plan.return_value = Plan(
        str({"services": {container_name: {"summary": "original plan"}}})
    )

    new_layer = Layer({"services": {container_name: {"summary": "original plan"}}})

    update_layer(container_name, mocked_container, new_layer, mocked_logger)

    mocked_container.get_plan.assert_called_once()
    mocked_container.replan.assert_not_called()


def test_pebble_error(mocked_container, mocked_logger):
    container_name = "test-container"
    mocked_container.get_plan.return_value = Plan(
        str({"services": {container_name: {"summary": "original plan"}}})
    )

    def side_effect():
        raise ChangeError("error message", "changelog")

    mocked_container.replan.side_effect = side_effect

    new_layer = Layer({"services": {container_name: {"summary": "new plan"}}})

    with pytest.raises(ErrorWithStatus):
        update_layer(container_name, mocked_container, new_layer, mocked_logger)
