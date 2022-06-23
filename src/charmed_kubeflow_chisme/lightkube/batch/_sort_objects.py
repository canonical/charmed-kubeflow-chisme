# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

# NOTE: These are temporary helpers.  They should be removed when
# [this pr](https://github.com/gtsystem/lightkube/pull/33/files) is merged into lightkube
# (and the min lightkube version of this package should be bumped accordingly)

from collections import defaultdict
from typing import List

from lightkube.core import resource


def _sort_objects(
    objs: List[resource.Resource], by: str = "kind", reverse: bool = False
) -> List[resource.Resource]:
    """Sorts a list of resource objects by a sorting schema, returning a new list.

    **parameters**
    * **objs** - list of resource objects to be sorted
    * **by** - *(optional)* sorting schema. Possible values:
        * **kind** - sorts by kind, ranking objects in an order that is suitable for batch-applying
          many resources.  For example, Namespaces and ServiceAccounts are sorted ahead of
          ClusterRoleBindings or Pods that might use them.  The reverse of this order is suitable
          for batch-deleting.
          See _kind_rank_function for full details on sorting
    * **reverse** - *(optional)* if `True`, sorts in reverse order
    """
    if by == "kind":
        objs = sorted(objs, key=_kind_rank_function, reverse=reverse)
    else:
        raise ValueError(f"Unknown sorting schema: {by}")
    return objs


UNKNOWN_ITEM_SORT_VALUE = 1000
APPLY_ORDER = defaultdict(lambda: UNKNOWN_ITEM_SORT_VALUE)
APPLY_ORDER["CustomResourceDefinition"] = 10
APPLY_ORDER["Namespace"] = 20
APPLY_ORDER["Secret"] = 31
APPLY_ORDER["ServiceAccount"] = 32
APPLY_ORDER["PersistentVolume"] = 33
APPLY_ORDER["PersistentVolumeClaim"] = 34
APPLY_ORDER["ConfigMap"] = 35
APPLY_ORDER["Role"] = 41
APPLY_ORDER["ClusterRole"] = 42
APPLY_ORDER["RoleBinding"] = 43
APPLY_ORDER["ClusterRoleBinding"] = 44


def _kind_rank_function(obj: List[resource.Resource]) -> int:
    """Returns an integer rank based on an objects .kind.

    Ranking is set to order kinds by:
    * CRDs
    * Namespaces
    * Things that might be referenced by pods (Secret, ServiceAccount, PVs/PVCs, ConfigMap)
    * RBAC
        * Roles and ClusterRoles
        * RoleBindings and ClusterRoleBindings
    * Everything else (Pod, Deployment, ...)
    """
    return APPLY_ORDER[obj.kind]
