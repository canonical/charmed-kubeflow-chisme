# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Iterable, TypeVar, Union

import lightkube
from lightkube.core import resource
from lightkube.core.exceptions import ApiError
from lightkube.core.resource import GlobalResource, NamespacedResource

# Replace with lightkube.sort_objects once gtsystem/lightkube#33 is merged
from ._sort_objects import _sort_objects as sort_objects

LOGGER = logging.getLogger(__name__)

GlobalResourceTypeVar = TypeVar("GlobalResource", bound=resource.GlobalResource)
GlobalSubResourceTypeVar = TypeVar("GlobalSubResource", bound=resource.GlobalSubResource)
NamespacedResourceTypeVar = TypeVar("NamespacedSubResource", bound=resource.NamespacedResource)


def apply_many(
    client: lightkube.Client,
    objs: Iterable[Union[GlobalResourceTypeVar, NamespacedResourceTypeVar]],
    field_manager: str = None,
    force: bool = False,
    logger: logging.Logger = None,
) -> Iterable[Union[GlobalResourceTypeVar, NamespacedResourceTypeVar]]:
    """Create or configure an iterable of Lightkube objects using client.apply().

    To avoid referencing objects before they are created, resources are sorted and applied in the
    following order:
    * CRDs
    * Namespaces
    * Things that might be referenced by pods (Secret, ServiceAccount, PVs/PVCs, ConfigMap)
    * RBAC
        * Roles and ClusterRoles
        * RoleBindings and ClusterRoleBindings
    * Everything else (Pod, Deployment, ...)

    Sorting is performed using Lightkube's `lightkube.codecs.sort_objects`

    Args:
        client: Lightkube client to use for applying resources
        objs: Iterable of objects to create. This need to be instances of a resource kind and have
              resource.metadata.namespaced defined if they are namespaced resources
        field_manager: Name associated with the actor or entity that is making these changes.
        force: *(optional)* Force is going to "force" Apply requests. It means user will
               re-acquire conflicting fields owned by other people.
        logger: *(optional)* Logger to use for applying resources

    Returns:
        A list of Resource objects returned from client.apply().  This list is returned in the
        order the resources were actually applied, not the order in which they're passed as inputs
        in `objs`.
    """
    logger = logger or LOGGER
    objs = sort_objects(objs)
    returns = [None] * len(objs)

    for i, obj in enumerate(objs):
        if isinstance(obj, NamespacedResource):
            namespace = obj.metadata.namespace
        elif isinstance(obj, GlobalResource):
            namespace = None
        else:
            raise TypeError(
                f"apply_many only supports objects of types NamespacedResource or GlobalResource,"
                f" got {type(obj)}"
            )
        logger.debug(f"Creating {obj.__class__} {obj.metadata.name}...")
        returns[i] = client.apply(
            obj=obj, namespace=namespace, field_manager=field_manager, force=force
        )
    return returns


def delete_many(
    client: lightkube.Client,
    objs: Iterable[Union[GlobalResourceTypeVar, NamespacedResourceTypeVar]],
    ignore_missing: bool = True,
    logger: logging.Logger = None,
) -> None:
    """Delete an iterable of objects using client.delete().

    To avoid deleting objects that are being used by others in the list (eg: deleting a CRD before
    deleting the CRs), resources are deleted in the reverse order as defined in apply_many

    Args:
        client: Lightkube Client to use for deletions
        objs: Iterable of objects to delete. This need to be instances of a resource kind and have
              resource.metadata.namespaced defined if they are namespaced resources
        ignore_missing: *(optional)* Avoid raising 404 errors on deletion (defaults to True)
        logger: *(optional)* Logger to use for deleting resources
    """
    logger = logger or LOGGER
    objs = sort_objects(objs, reverse=True)
    exceptions = []

    for obj in objs:
        if isinstance(obj, NamespacedResource):
            namespace = obj.metadata.namespace
        elif isinstance(obj, GlobalResource):
            namespace = None
        else:
            raise TypeError(
                "delete_many only supports objects of types NamespacedResource or GlobalResource,"
                f" got {type(obj)}"
            )
        try:
            logger.debug(f"Deleting {obj.__class__} {obj.metadata.name}...")
            client.delete(res=obj.__class__, name=obj.metadata.name, namespace=namespace)
        except ApiError as error:
            if error.status.code == 404 and ignore_missing:
                logger.debug(
                    f"{obj.__class__} {obj.metadata.name} not found! Ignoring because"
                    f" ignore_missing={ignore_missing}."
                )
            else:
                logger.debug(f"Failed to delete {obj.__class__} {obj.metadata.name}: {error}")
                exceptions.append(error)

    if exceptions:
        raise RuntimeError("Deleting K8s resources completed with errors", exceptions)
