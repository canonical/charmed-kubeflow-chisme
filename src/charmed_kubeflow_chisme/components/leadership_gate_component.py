# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""Reusable Component for blocking when not a leader."""
import logging

from ops import ActiveStatus, StatusBase, WaitingStatus

from charmed_kubeflow_chisme.components.component import Component

logger = logging.getLogger(__name__)


class LeadershipGateComponent(Component):
    """This Component checks that we are the leader, otherwise sets WaitingStatus.

    TODO: This is a hack to let charms function like they have traditionally in Kubeflow.  A more
     nuanced way to handle this would be to use the Component.configure_app/configure_unit methods,
     similar to how Sunbeam does this.  But until that is thought through, this is an easy
     implementation.
    """

    def ready_for_execution(self) -> bool:
        """Returns True if this is the leader, else False."""
        return self._charm.unit.is_leader()

    def get_status(self) -> StatusBase:
        """Returns the status of this Component."""
        if not self._charm.unit.is_leader():
            return WaitingStatus("Waiting for leadership")

        return ActiveStatus()
