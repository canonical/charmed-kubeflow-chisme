# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from lightkube.resources.apps_v1 import StatefulSet
from ops.model import WaitingStatus

from ..exceptions import ReplicasNotReadyError


def validate_statefulset(resource: StatefulSet) -> bool:
    """Returns True if the StatefulSet is ready, else raises an Exception."""
    ready_replicas = resource.status.ready_replicas
    replicas_expected = resource.spec.replicas
    if ready_replicas != replicas_expected:
        error_message = (
            f"StatefulSet {resource.metadata.name} in namespace "
            f"{resource.metadata.namespace} has {ready_replicas} readyReplicas, "
            f"expected {replicas_expected}"
        )
        raise ReplicasNotReadyError(error_message, WaitingStatus)

    return True
