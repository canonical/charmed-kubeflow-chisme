# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from contextlib import nullcontext
from unittest import mock
from unittest.mock import MagicMock

import pytest
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, StatusBase, WaitingStatus
from ops.pebble import CheckInfo, CheckLevel, CheckStatus

from charmed_kubeflow_chisme.exceptions import ErrorWithStatus
from charmed_kubeflow_chisme.status_handling import check_workload_health, get_first_worst_error, set_and_log_status


BlockedError1 = ErrorWithStatus("Blocked1", BlockedStatus)
BlockedError2 = ErrorWithStatus("Blocked2", BlockedStatus)
WaitingError = ErrorWithStatus("Waiting", WaitingStatus)


@pytest.mark.parametrize(
    "errors,expected_returned_error,context_raised",
    (
        # return None when no errors exist
        ([], None, nullcontext()),
        ([None], None, nullcontext()),
        # return None if errors do not have .status
        ([Exception("does not have a status")], None, nullcontext()),
        # Raises if input not iterable
        (1, None, pytest.raises(TypeError)),
        # return valid Exceptions, ignoring Nones
        ([None, BlockedError1, None], BlockedError1, nullcontext()),
        ([None, WaitingError, None], WaitingError, nullcontext()),
        # Return Blocked instead of Waiting, regardless of order
        ([BlockedError1, WaitingError], BlockedError1, nullcontext()),
        ([WaitingError, BlockedError1], BlockedError1, nullcontext()),
        # Return the first Blocked, even if there are other errors.
        ([WaitingError, BlockedError2, BlockedError1], BlockedError2, nullcontext()),
    ),
)
def test_get_first_worst_error(errors, expected_returned_error, context_raised):
    with context_raised:
        error = get_first_worst_error(errors=errors)
        assert error == expected_returned_error


@pytest.mark.parametrize(
    "type, message, expected_level",
    [
        (ActiveStatus, "ActiveStatus, we should log.info!", "INFO"),
        (BlockedStatus, "BlockedStatus, we should log.warning!", "WARNING"),
        (MaintenanceStatus, "MaintenanceStatus, we should log.info", "INFO"),
        (WaitingStatus, "WaitingStatus, we should log.info!", "INFO"),
    ],
)
def test_set_and_log_status(type: StatusBase, message: str, expected_level: str, caplog):
    mock_unit = MagicMock()
    logger = logging.getLogger()
    status = type(message)
    set_and_log_status(mock_unit, logger, status)

    assert mock_unit.status == status
    assert [message] == [rec.message for rec in caplog.records]
    assert [expected_level] == [rec.levelname for rec in caplog.records]


def test_check_workload_health_check_up(
    mocked_container,
    caplog,
):
    container_name = "test-container"
    health_check = "up"
    mocked_container.get_check.return_value = CheckInfo(
        name="up", status=CheckStatus.UP, level=CheckLevel.ALIVE, failures=0, threshold=3
    )
    logger = logging.getLogger()

    check_workload_health(mocked_container, container_name, health_check, logger)


def test_check_workload_health_check_down(
    mocked_container,
    caplog,
):
    container_name = "test-container"
    health_check = "up"
    mocked_container.get_check.return_value = CheckInfo(
        name="up", status=CheckStatus.DOWN, level=CheckLevel.ALIVE, failures=0, threshold=3
    )
    logger = logging.getLogger()

    with pytest.raises(ErrorWithStatus):
        check_workload_health(mocked_container, container_name, health_check, logger)
    assert ["Container test-container failed health check."] == [
        rec.message for rec in caplog.records
    ]
    assert ["ERROR"] == [rec.levelname for rec in caplog.records]


@pytest.fixture()
def mocked_container(mocker):
    mocked_container = mocker.patch("ops.model.Container")
    mocked_container.return_value = mock.MagicMock()
    yield mocked_container
