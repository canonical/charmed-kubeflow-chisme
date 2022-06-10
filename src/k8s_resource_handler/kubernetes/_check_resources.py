# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import List

import lightkube
from lightkube.core.resource import GlobalResource
from lightkube.resources.apps_v1 import StatefulSet
from ops.model import BlockedStatus

from ..exceptions import ErrorWithStatus, ReplicasNotReadyError, ResourceNotFoundError
from ._validate_statefulset import validate_statefulset
from ..types import LightkubeResourceType, LightkubeResourcesList


def check_resources(
    client: lightkube.Client, resources: LightkubeResourcesList
) -> (bool, List[ErrorWithStatus]):
    """Checks status of resources in cluster, returning True if all are considered ready.

    Also returns a list of any Exceptions encountered due to failed resource checks.  If
    len(resources)==0, this returns a status of True.

    Note: This is a basic skeleton of a true check on the resources.  Currently it only checks
    that resources exist and that StatefulSets have their desired number of replicas ready.

    Returns: Tuple of:
        Status (bool)
        List of Exceptions encountered during failed checks, with each entry
        indexed the same as the corresponding expected_resource (list[str])
    """
    errors: list = [None] * len(resources)
    for i, expected_resource in enumerate(resources):
        try:
            found_resource = _get_resource_or_error(client, expected_resource)
        except ResourceNotFoundError as e:
            errors[i] = e
            continue

        if isinstance(found_resource, StatefulSet):
            try:
                validate_statefulset(found_resource)
            except ReplicasNotReadyError as e:
                errors[i] = e

    return not any(errors), errors


def _get_resource_or_error(client: lightkube.Client, resource: LightkubeResourceType) -> LightkubeResourceType:
    """Returns a Resource from a Client, raising a ResourceNotFoundError if not found"""
    try:
        return client.get(
            type(resource),
            resource.metadata.name,
            namespace=resource.metadata.namespace,
        )
    except lightkube.core.exceptions.ApiError:
        msg = f"Cannot find k8s object corresponding to '{resource.metadata}'"
        raise ResourceNotFoundError(msg, BlockedStatus)
