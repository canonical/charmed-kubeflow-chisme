# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from ._with_status import ErrorWithStatus


class ResourceNotFoundError(ErrorWithStatus):
    """Raised if a Kubernetes resource is not found."""

    pass


class ReplicasNotReadyError(ErrorWithStatus):
    """Raised if a Kubernetes resource does not have its required replicas ready."""

    pass
