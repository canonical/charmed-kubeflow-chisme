# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Union, Iterable, TypeVar

import lightkube
from lightkube.core import resource
from lightkube.core.resource import NamespacedResource, GlobalResource

from ._sort_objects import _sort_objects


GlobalResourceTypeVar = TypeVar('GlobalResource', bound=resource.GlobalResource)
GlobalSubResourceTypeVar = TypeVar('GlobalSubResource', bound=resource.GlobalSubResource)
NamespacedResourceTypeVar = TypeVar('NamespacedSubResource', bound=resource.NamespacedResource)


def apply_many(client: lightkube.Client, objs: Iterable[Union[GlobalResourceTypeVar, NamespacedResourceTypeVar]],
               field_manager: str = None, force: bool = False) -> Iterable[Union[GlobalResourceTypeVar, NamespacedResourceTypeVar]]:
    """Create or configure an iterable of objects using client.apply()

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
        objs:  iterable of objects to create. This need to be instances of a resource kind and have
               resource.metadata.namespaced defined if they are namespaced resources
        field_manager: Name associated with the actor or entity that is making these changes.
        force: *(optional)* Force is going to "force" Apply requests. It means user will re-acquire conflicting
               fields owned by other people.
    """
    objs = _sort_objects(objs)
    returns = [None] * len(objs)

    for i, obj in enumerate(objs):
        if isinstance(obj, NamespacedResource):
            namespace = obj.metadata.namespace
        elif isinstance(obj, GlobalResource):
            namespace = None
        else:
            raise TypeError("apply_many only supports objects of types NamespacedResource or GlobalResource")
        returns[i] = client.apply(obj, namespace=namespace, field_manager=field_manager, force=force)
    return returns


def delete_many(client: lightkube.Client, objs: Iterable[Union[GlobalResourceTypeVar, NamespacedResourceTypeVar]]) -> None:
    """Delete an iterable of objects using client.delete()

    To avoid deleting objects that are being used by others in the list (eg: deleting a CRD before deleting the CRs),
    resources are deleted in the reverse order as defined in apply_many

    Args:
        client: Lightkube Client to use for deletions
        objs:  iterable of objects to delete. This need to be instances of a resource kind and have
               resource.metadata.namespaced defined if they are namespaced resources
    """
    objs = _sort_objects(objs, reverse=True)

    for i, obj in enumerate(objs):
        if isinstance(obj, NamespacedResource):
            namespace = obj.metadata.namespace
        elif isinstance(obj, GlobalResource):
            namespace = None
        else:
            raise TypeError("delete_many only supports objects of types NamespacedResource or GlobalResource")

        client.delete(obj, name=obj.metadata.name, namespace=namespace)