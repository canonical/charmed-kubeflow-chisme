# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Component for gating a charm based on the count of active relations."""

import logging
from typing import List

from ops import ActiveStatus, BlockedStatus, StatusBase

from charmed_kubeflow_chisme.components import Component

logger = logging.getLogger(__name__)


class RelationCountGateComponent(Component):
    """Component that gates the charm based on the count of active watched relations.

    Blocks the charm when the number of simultaneously active relations from
    ``relation_names`` falls outside the range
    [minimum_related_applications, maximum_related_applications].
    """

    def __init__(
        self,
        *args,
        relation_names: List[str],
        minimum_related_applications: int = 1,
        maximum_related_applications: int = 1,
        **kwargs,
    ):
        """Initialise the component.

        Args:
            relation_names: Names of the relations to watch.
            minimum_related_applications: Minimum number of watched relations that must be
                active. Defaults to 1.
            maximum_related_applications: Maximum number of watched relations allowed to be
                active simultaneously. Defaults to 1.

        Raises:
            ValueError: If either bound is negative, or if minimum exceeds maximum.
        """
        if minimum_related_applications < 0:
            raise ValueError(
                f"minimum_related_applications must be non-negative, "
                f"got {minimum_related_applications}."
            )
        if maximum_related_applications < 0:
            raise ValueError(
                f"maximum_related_applications must be non-negative, "
                f"got {maximum_related_applications}."
            )
        if minimum_related_applications > maximum_related_applications:
            raise ValueError(
                f"minimum_related_applications ({minimum_related_applications}) must not "
                f"exceed maximum_related_applications ({maximum_related_applications})."
            )

        super().__init__(*args, **kwargs)
        self.relation_names = relation_names
        self.minimum_related_applications = minimum_related_applications
        self.maximum_related_applications = maximum_related_applications

    def get_status(self) -> StatusBase:
        """Check that the number of active watched relations is within the configured range."""
        active_relations = [
            name
            for name in self.relation_names
            if self._charm.model.get_relation(name) is not None
        ]
        active_relations_number = len(active_relations)

        if active_relations_number < self.minimum_related_applications:
            relations_str = ", ".join(f"'{r}'" for r in self.relation_names)
            logger.error(
                f"Too few relations are active ({active_relations_number}); "
                f"need at least {self.minimum_related_applications} of: {relations_str}."
            )
            return BlockedStatus(
                f"Too few relations active: need at least "
                f"{self.minimum_related_applications} of {relations_str}. "
                "Add a relation to unblock."
            )

        if active_relations_number > self.maximum_related_applications:
            active_str = ", ".join(f"'{r}'" for r in active_relations)
            logger.error(
                f"Too many watched relations are active ({active_str}); "
                f"at most {self.maximum_related_applications} may be active simultaneously."
            )
            return BlockedStatus(
                f"Too many conflicting relations are present: {active_str}. "
                "Remove some to unblock."
            )

        return ActiveStatus()
