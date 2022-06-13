# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from contextlib import nullcontext

import pytest
from ops.model import BlockedStatus, WaitingStatus

from k8s_resource_handler.exceptions import ErrorWithStatus
from k8s_resource_handler.status_handling import get_first_worst_error

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
