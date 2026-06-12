# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Component for interacting with S3-compatible object storage via the s3 interface.

This component uses the Requirer side of the object-storage charm library.
See: https://github.com/canonical/object-storage-integrator/tree/main/s3
"""

import logging

from object_storage import S3Requirer
from ops import ActiveStatus, BlockedStatus, StatusBase

from charmed_kubeflow_chisme.components.component import Component

logger = logging.getLogger(__name__)


class S3RequirerComponent(Component):
    """Component that manages an S3-compatible object storage relation.

    ``get_data()`` returns connection info for every related application that has published
    at least some relation data. ``get_status()`` returns Active only when all related
    applications have published all required relation fields.
    """

    def __init__(
        self,
        *args,
        relation_name: str,
        is_optional: bool = False,
        required_relation_fields: frozenset[str] = frozenset({"access-key", "secret-key"}),
        **kwargs,
    ):
        """Initialise the component.

        Args:
            relation_name: Name of the S3 relation endpoint.
            is_optional: When True, the component is Active even if no relation is present.
            required_relation_fields: Set of databag keys that must all be present for a
                relation to be considered fully populated. Defaults to the standard S3
                fields ``{"access-key", "secret-key"}``. See:
                https://github.com/canonical/object-storage-integrator/blob/dcbe3071598e599a7874373e2c93459b14436a94/lib/object_storage/s3.py#L20-L23
        """
        super().__init__(*args, **kwargs)
        self.relation_name = relation_name
        self.is_optional = is_optional
        self.required_relation_fields = required_relation_fields
        self.s3_client = S3Requirer(
            charm=self._charm,
            relation_name=relation_name,
        )
        self._events_to_observe = [
            self._charm.on[self.relation_name].relation_changed,
            self._charm.on[self.relation_name].relation_broken,
        ]

    def get_data(self) -> list[dict]:
        """Return S3 connection info for all related applications that have published any data.

        Returns a list with one entry per related application that has published
        at least some data. Applications that are related but have not yet published
        any data are excluded.
        """
        return [
            info
            for relation in self._charm.model.relations[self.relation_name]
            if (info := self.s3_client.get_storage_connection_info(relation))
        ]

    def get_status(self) -> StatusBase:
        """Return Active if all related applications have published required data, Blocked if not.

        For optional relations, Active is returned when no relation is present.
        If any related application has not yet published all required relation fields,
        Blocked is returned.
        """
        relations = self._charm.model.relations[self.relation_name]

        if not relations:
            if self.is_optional:
                return ActiveStatus()
            return BlockedStatus(f"Please add the missing relation: {self.relation_name}")

        for relation in relations:
            info = self.s3_client.get_storage_connection_info(relation)
            if not info or not self.required_relation_fields.issubset(info):
                return BlockedStatus(
                    f"Relation '{self.relation_name}' is present but required data is not yet available."
                )

        return ActiveStatus()
