# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# From prototype for stateless multi-status handling
# https://github.com/benhoyt/test-charms/blob/statustest-stateless/statustest/src/multistatus.py
"""Status prioritiser."""

import logging
import typing
from typing import List, Tuple

import ops
from ops import EventBase, Framework, Unit

logger = logging.getLogger(__name__)


class Prioritiser:
    """Status prioritiser: track the highest-priority status among several components."""

    _PRIORITIES = {
        "error": 0,
        "blocked": 1,
        "waiting": 2,
        "maintenance": 3,
        "active": 4,
        "unknown": 5,
    }

    def __init__(self):
        self._components = {}

    def add(self, component: str, get_status: typing.Callable[[], ops.StatusBase]):
        """Add a named status component."""
        if component in self._components:
            raise ValueError(f"duplicate component {component!r}")
        self._components[component] = get_status

    def highest(self) -> ops.StatusBase:
        """Return highest-priority status with message prefixed with component name."""
        statuses = self.all()
        if not statuses:
            return ops.UnknownStatus()
        component, status = statuses[0]
        if isinstance(status, ops.ActiveStatus) and not status.message:
            return ops.ActiveStatus()
        return ops.StatusBase.from_name(status.name, f"[{component}] {status.message}")

    def install(self, framework: Framework, unit: Unit):
        """Installs this instance onto the framework events required.

        TODO: This doesn't work because framework.observe's observer parameter (the last one)
         only accepts methods, not functions?  For now, use the hack of implementing this
         directly in the charm main.
        """

        def update_unit_status(event: EventBase):
            logger.info("Executing Prioritizer.update_unit_status")
            unit.status = self.highest()

        framework.observe(framework.on.commit, update_unit_status)

    def _on_commit(self, event):
        self.unit.status = self.prioritiser.highest()

    def all(self) -> List[Tuple[str, ops.StatusBase]]:
        """Return list of (component_name, status) tuples for all components.

        The list is ordered highest-priority first. If there are two statuses
        with the same level, components added first come first.
        """
        # TODO: exception handling (log full details and yield ErrorStatus?)
        statuses = [
            (component, get_status()) for component, get_status in self._components.items()
        ]
        statuses.sort(key=lambda s: self._PRIORITIES[s[1].name])
        return statuses
