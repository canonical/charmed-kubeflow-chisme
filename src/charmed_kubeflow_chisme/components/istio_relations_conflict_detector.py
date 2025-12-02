# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Component to detect conflicting Istio relations."""

import logging

from ops import ActiveStatus, BlockedStatus, StatusBase

from charmed_kubeflow_chisme.components import Component

logger = logging.getLogger(__name__)


class IstioRelationsConflictDetectorComponent(Component):
    """Component to detect conflicting Istio relations."""

    def __init__(
        self,
        *args,
        sidecar_relation_name: str = "ingress",
        ambient_relation_name: str = "istio-ingress-route",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.sidecar_relation_name = sidecar_relation_name
        self.ambient_relation_name = ambient_relation_name

    def get_status(self) -> StatusBase:
        """Return the status of the component.

        If both sidecar and ambient relations are present, return BlockedStatus.
        Otherwise, return ActiveStatus.
        """
        ambient_relation = self._charm.model.get_relation(self.ambient_relation_name)
        sidecar_relation = self._charm.model.get_relation(self.sidecar_relation_name)

        if ambient_relation and sidecar_relation:
            logger.error(
                "Both 'istio-ingress-route' and 'ingress' relations are present, "
                "remove one to unblock."
            )
            return BlockedStatus(
                "Cannot have both 'istio-ingress-route' and 'ingress' relations "
                "at the same time.",
            )
        return ActiveStatus()
