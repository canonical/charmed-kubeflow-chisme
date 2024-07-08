# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""Reusable Component for blocking when specified CRDs are not present."""
import logging
from typing import List

from lightkube import Client
from lightkube.core.exceptions import ApiError
from lightkube.resources.apiextensions_v1 import CustomResourceDefinition
from ops import ActiveStatus, BlockedStatus, StatusBase

from charmed_kubeflow_chisme.components.component import Component

logger = logging.getLogger(__name__)


class CRDsGateComponent(Component):
    """This Component checks that the specified CRDs are present in the cluster."""

    def __init__(self, charm, name, crds: List[str], lightkube_client=None):
        super().__init__(charm, name)
        self._charm = charm
        self._crds = crds
        self._lightkube_client = lightkube_client or Client()

    def _crd_exists(self, crd_name: str) -> bool:
        """Check if a specific CRD exists in the cluster."""
        try:
            self._lightkube_client.get(CustomResourceDefinition, crd_name)
            return True
        except ApiError as e:
            if e.status.reason == "NotFound":
                return False
            raise

    def ready_for_execution(self) -> bool:
        """Returns True if all specified CRDs exist, else False."""
        return all(self._crd_exists(crd) for crd in self._crds)

    def get_status(self) -> StatusBase:
        """Returns the status of this Component."""
        missing_crds = [crd for crd in self._crds if not self._crd_exists(crd)]
        if missing_crds:
            return BlockedStatus(f"Missing CRDs: {', '.join(missing_crds)}")

        return ActiveStatus()
