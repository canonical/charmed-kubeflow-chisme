# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""A wrapper around a Component for use in a ComponentGraph."""

from __future__ import (
    annotations,  # To enable type hinting a method in a class with its own class
)

from typing import List, Optional

from ops import ActiveStatus, MaintenanceStatus, StatusBase

from .component import Component


class ComponentGraphItem:
    """A wrapper around a Component for use in a ComponentGraph."""

    def __init__(
        self,
        component: Component,
        depends_on: Optional[List[ComponentGraphItem]] = None,
    ):
        self.component = component
        self.name = self.component.name
        self.depends_on = depends_on or []
        self._executed: bool = False

    @property
    def events_to_observe(self) -> List[str]:
        """Returns a list of the names of extra events that this Component should observe."""
        return self.component.events_to_observe

    @property
    def executed(self) -> bool:
        """Returns whether this Component has already been executed."""
        return self._executed

    @executed.setter
    def executed(self, value: bool):
        if value not in [True, False]:
            raise ValueError(f"Executed must be either True or False - got {value}.")
        self._executed = value

    @property
    def ready_for_execution(self) -> bool:
        """Returns whether this Component is ready for execution.

        A Component is ready for execution if:
        * it has not previously been executed
        * all Components it depends_on have been executed and gone to ActiveStatus
        """
        if len(self._inactive_prerequisites()) != 0:
            return False
        if self._executed:
            return False
        return True

    @property
    def status(self) -> StatusBase:
        """Returns the Status of this Component in the context of Components it depends_on.

        If any depends_on Component is not in ActiveStatus, this returns a MaintenanceStatus
        indicating what is being waited on.

        If all depends_on Components are in ActiveStatus and this Component has not executed,
        returns a MaintenanceStatus indicating it is waiting to be executed.

        If all depends_on Components are in ActiveStatus and this Component has been executed,
        returns the Status for this Component
        """
        missing_prerequisites = {
            prerequisite.name: prerequisite.status
            for prerequisite in self._inactive_prerequisites()
        }

        if missing_prerequisites:
            message_suffix = ", ".join(
                [f"{name} ({status})" for name, status in missing_prerequisites.items()]
            )
            return MaintenanceStatus(f"Execution pending - waiting on {message_suffix}.")

        if not self.executed:
            return MaintenanceStatus("Execution pending.")

        return self.component.status

    def _inactive_prerequisites(self) -> List[ComponentGraphItem]:
        """Returns a list of any depends_on ComponentGraphItems that are not yet ActiveStatus."""
        return [
            prerequisite
            for prerequisite in self.depends_on
            if not isinstance(prerequisite.status, ActiveStatus)
        ]
