from typing import List, Union, Tuple

import lightkube
from lightkube.core.resource import NamespacedResource, GlobalResource
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import WaitingStatus, BlockedStatus

from ..exceptions import ResourceNotFoundError, ReplicasNotReadyError
from ...exceptions import ErrorWithStatus


def check_resources(client: lightkube.Client, expected_resources: List[Union[NamespacedResource, GlobalResource]]) -> \
        (bool, List[ErrorWithStatus]):
    """Checks status of resources in cluster, returning True if all are considered ready

    Note: This is a basic skeleton of a true check on the resources.  Currently it only checks
    that resources exist and that StatefulSets have their desired number of replicas ready.

    Returns: Tuple of:
        Status (bool)
        List of Exceptions encountered during failed checks, with each entry
        indexed the same as the corresponding expected_resource (list[str])
    """
    errors: list = [None] * len(expected_resources)
    for i, expected_resource in enumerate(expected_resources):
        try:
            found_resource = client.get(
                type(expected_resource),
                expected_resource.metadata.name,
                namespace=expected_resource.metadata.namespace,
            )
        except lightkube.core.exceptions.ApiError as e:
            msg = f"Cannot find k8s object corresponding to '{expected_resource.metadata}'"
            errors[i] = ResourceNotFoundError(msg, BlockedStatus)
            continue

        if isinstance(found_resource, StatefulSet):
            try:
                validate_statefulset(found_resource)
            except ReplicasNotReadyError as e:
                errors[i] = e

    return not any(errors), errors


def validate_statefulset(resource: StatefulSet) -> bool:
    """Returns True if the StatefulSet is ready, else raises an Exception"""
    readyReplicas = resource.status.ready_replicas
    replicas_expected = resource.spec.replicas
    if readyReplicas != replicas_expected:
        error_message = (
            f"StatefulSet {resource.metadata.name} in namespace "
            f"{resource.metadata.namespace} has {readyReplicas} readyReplicas, "
            f"expected {replicas_expected}"
        )
        raise ReplicasNotReadyError(error_message, WaitingStatus)

    return True


def get_first_worst_error(errors: List[ErrorWithStatus]) -> ErrorWithStatus:
    """Returns the first of the worst errors in the list, ranked by their status

    Raises if List contains no Exceptions, or if any Exception does not have a .status

    Status are ranked, starting with the worst:
        BlockedStatus
        WaitingStatus
    """
    cached_error = None

    for error in errors:
        if error is None:
            continue

        if isinstance(error.status, BlockedStatus):
            return error
        elif isinstance(error.status, WaitingStatus):
            cached_error = error

    return cached_error
