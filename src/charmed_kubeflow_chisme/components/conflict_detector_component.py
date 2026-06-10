# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
"""Component for detecting mutually exclusive relations."""

import logging
from typing import List

from ops import ActiveStatus, BlockedStatus, StatusBase

from charmed_kubeflow_chisme.components import Component

logger = logging.getLogger(__name__)


class ConflictDetectorComponent(Component):
    """Component to detect mutually exclusive relations that must not be present simultaneously."""

    def __init__(
        self,
        *args,
        relation_names: List[str],
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.relation_names = relation_names

    def get_status(self) -> StatusBase:
        """Check that at most one of the configured relations is present at a time."""
        active_relations = [
            name
            for name in self.relation_names
            if self._charm.model.get_relation(name) is not None
        ]

        if len(active_relations) > 1:
            relations_str = ", ".join(f"'{r}'" for r in active_relations)
            logger.error(
                f"Multiple conflicting relations are present ({relations_str}), "
                "remove all but one to unblock."
            )
            return BlockedStatus(
                f"Multiple conflicting relations are present: {relations_str}. "
                "Remove all but one to unblock."
            )
        return ActiveStatus()
