# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Component for interacting with S3-compatible object storage via the s3 interface.

This component uses the Requirer side of the object-storage charm library.
See: https://github.com/canonical/object-storage-integrator/tree/main/s3
"""

import logging
from typing import Optional

from object_storage import S3Requirer
from ops import ActiveStatus, BlockedStatus, StatusBase

from charmed_kubeflow_chisme.components.component import Component

logger = logging.getLogger(__name__)


class S3Component(Component):
    """Component that manages an S3-compatible object storage relation."""

    def __init__(
        self,
        *args,
        relation_name: str,
        is_optional: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.relation_name = relation_name
        self.is_optional = is_optional
        self.s3_client = S3Requirer(
            charm=self._charm,
            relation_name=relation_name,
        )

    def get_data(self) -> Optional[dict]:
        """Return the S3 connection info from the relation data, or None if unavailable."""
        return self.s3_client.get_storage_connection_info()

    def get_status(self) -> StatusBase:
        """Return Active if relation data is available, Blocked otherwise.

        For optional relations, Active is returned when no relation is present.
        If a relation is present, data must also be available to return Active.
        """
        relation = self._charm.model.get_relation(self.relation_name)

        if not relation:
            if self.is_optional:
                return ActiveStatus()
            return BlockedStatus(f"Please add the missing relation: {self.relation_name}")

        if not self.get_data():
            return BlockedStatus(
                f"Relation '{self.relation_name}' is present but contains no data."
            )

        return ActiveStatus()
