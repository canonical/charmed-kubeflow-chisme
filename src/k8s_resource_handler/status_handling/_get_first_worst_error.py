# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import List

from ops.model import BlockedStatus, WaitingStatus

from ..exceptions import ErrorWithStatus


def get_first_worst_error(errors: List[ErrorWithStatus]) -> ErrorWithStatus:
    """Returns the first of the worst errors in the list, ranked by their status.

    Raises if List contains no Exceptions, or if any Exception does not have a .status

    Status are ranked, starting with the worst:
        BlockedStatus
        WaitingStatus
    """
    cached_error = None

    for error in errors:
        try:
            if isinstance(error.status, BlockedStatus):
                return error
            elif isinstance(error.status, WaitingStatus):
                cached_error = error
        except AttributeError:
            continue

    return cached_error
