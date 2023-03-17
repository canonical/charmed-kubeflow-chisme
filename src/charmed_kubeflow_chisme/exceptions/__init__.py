# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""A collection of standard Exceptions for use when writing charms."""

from ._generic_charm_runtime_error import GenericCharmRuntimeError
from ._kubernetes import ReplicasNotReadyError, ResourceNotFoundError
from ._with_status import ErrorWithStatus

__all__ = [
    ReplicasNotReadyError,
    ResourceNotFoundError,
    ErrorWithStatus,
    GenericCharmRuntimeError,
]
