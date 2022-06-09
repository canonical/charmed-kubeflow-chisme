# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from ops.model import BlockedStatus

from ..types import CharmStatusType
from . import ErrorWithStatus


class ResourceNotFoundError(ErrorWithStatus):
    """Raised if a Kubernetes resource is not found."""

    pass


class ReplicasNotReadyError(ErrorWithStatus):
    """Raised if a Kubernetes resource does not have its required replicas ready."""

    pass


class ReconcileError(ErrorWithStatus):
    """Raised if a Kubernetes Manifest charm fails to reconcile."""

    def __init__(
        self,
        msg: str = "Failed to reconcile charm resources",
        status_type: CharmStatusType = BlockedStatus,
    ):
        super().__init__(msg, status_type)
