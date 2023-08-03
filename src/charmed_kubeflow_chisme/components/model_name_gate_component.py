# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""Reusable Component for blocking when model name is not the expected."""
import logging

from ops import ActiveStatus, BlockedStatus, StatusBase

from charmed_kubeflow_chisme.components.component import Component

logger = logging.getLogger(__name__)


class ModelNameGateComponent(Component):
    """Raises BlockedStatus if the model name is not the expected, according to arguments."""

    def __init__(
        self,
        *args,
        model_name: str,
        **kwargs,
    ):
        """Reusable Component for blocking when model name is not the expected."""
        super().__init__(*args, **kwargs)
        self.model_name = model_name

    def ready_for_execution(self) -> bool:
        """Returns True if charm is deployed to the required model, else False."""
        return self._charm.model.name == self.model_name

    def get_status(self) -> StatusBase:
        """Returns Active if charm is deployed to the required model, else Blocked."""
        if self._charm.model.name != self.model_name:
            return BlockedStatus(f"Charm must be deployed to model named {self.model_name}")

        return ActiveStatus()
