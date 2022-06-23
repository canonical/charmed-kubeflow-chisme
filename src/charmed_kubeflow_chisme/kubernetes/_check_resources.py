# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import List

import lightkube
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import BlockedStatus

from ..exceptions import ErrorWithStatus, ReplicasNotReadyError, ResourceNotFoundError
from ..types import LightkubeResourcesList, LightkubeResourceType
from ._validate_statefulset import validate_statefulset


def check_resources(
    client: lightkube.Client, resources: LightkubeResourcesList
) -> (bool, List[ErrorWithStatus]):
    """Checks status of a list of resources.

    Checks each resource in expected_resources to confirm it is in a "ready" state.  The definition
    of "ready" depends on the resource:
    * For all resources: checks whether the resource exists
    * For StatefulSets: checks whether the number of desired replicas equals their ready replicas
    For each resource that is not "ready", an ErrorWithStatus is returned that contains more
    details.

    TODO: This is a skeleton of a true check on resources, applying only basic checks.  This could
          be extended to do more detailed checks on other resource types.

    Returns: Tuple of:
        Status (bool): True if all resources are ready, else False
        List of Exceptions encountered during failed checks, with each entry
        indexed the same as the corresponding expected_resource (list[str])
    """
    errors: list = [None] * len(resources)
    for i, expected_resource in enumerate(resources):
        try:
            found_resource = _get_resource(client, expected_resource)
        except ResourceNotFoundError as e:
            errors[i] = e
            continue

        if isinstance(found_resource, StatefulSet):
            try:
                validate_statefulset(found_resource)
            except ReplicasNotReadyError as e:
                errors[i] = e

    return not any(errors), errors


def _get_resource(
    client: lightkube.Client, resource: LightkubeResourceType
) -> LightkubeResourceType:
    """Returns a Resource from a Client, raising a ResourceNotFoundError if not found."""
    try:
        return client.get(
            type(resource),
            resource.metadata.name,
            namespace=resource.metadata.namespace,
        )
    except lightkube.core.exceptions.ApiError:
        msg = f"Cannot find k8s object corresponding to '{resource.metadata}'"
        raise ResourceNotFoundError(msg, BlockedStatus)
