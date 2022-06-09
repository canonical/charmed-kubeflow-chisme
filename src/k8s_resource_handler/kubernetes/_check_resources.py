from typing import List, Union

import lightkube
from lightkube.core.resource import GlobalResource, NamespacedResource
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import BlockedStatus

from ..exceptions import ErrorWithStatus, ReplicasNotReadyError, ResourceNotFoundError
from ._validate_statefulset import validate_statefulset


def check_resources(
    client: lightkube.Client, expected_resources: List[Union[NamespacedResource, GlobalResource]]
) -> (bool, List[ErrorWithStatus]):
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
