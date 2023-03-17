# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""A collection of standard Exceptions for use when writing charms."""

from ._kubernetes import ReplicasNotReadyError, ResourceNotFoundError
from ._with_status import ErrorWithStatus
from ._error_status_with_message import UnitErrorStatusWithMessage

__all__ = [ReplicasNotReadyError, ResourceNotFoundError, ErrorWithStatus]
