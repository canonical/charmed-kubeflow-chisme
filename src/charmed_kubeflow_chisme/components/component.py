# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""Abstract class defining the API needed for an atomic piece of work that a charm does."""
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional

from ops import ActiveStatus, BoundEvent, CharmBase, Object, StatusBase


class Component(Object, ABC):
    """Abstract class defining the API needed for an atomic piece of work that a charm does.

    This is intended to be extended for different types of operations, such as managing Pebble
    containers or relation libraries.
    """

    def __init__(
        self, charm: CharmBase, name: str, inputs_getter: Optional[Callable[[], Any]] = None
    ):
        """Instantiate a Component.

        Args:
            charm: (from ops.Object's `framework` parameter) Charm that will be the parent of the
                   Charm framework events related to this Component.
                   Note that this can also accept a Framework object, although this is probably
                   useful only in unit tests.
            name: Unique name of this instance of the class.  This is used as the ops.Object key
                  argument, as well as for some status/debug printing.
            inputs_getter: (optional) a function that returns an object with inputs that can be
                           used in the component.  Needed only when instantiating objects that
                           required data that is not available until later during runtime, like
                           passing data from a one Component to another.
        """
        super().__init__(parent=charm, key=name)
        self.name = name  # Will be the same as self.handle.key
        self._charm = charm
        self._events_to_observe: List[BoundEvent] = []
        self._inputs_getter = inputs_getter

    # Methods that can be used directly from the Component class for most cases
    def configure_charm(self, event):
        """Public API to get this Component to do whatever it should with an Event.

        Generally, this should not need modification.  Instead, implement the Component's logic in
        one or more of:
        * _configure_unit: for work executed on every unit in an application
        * _configure_app_leader: for work executed on only the leader of an application
        * _configure_app_non_leader: for work executed on only the non-leaders of an application
        """
        self._configure_unit(event)
        self._configure_app(event)

    @property
    def ready(self) -> bool:
        """Returns boolean indicating if Component is ready (Active)."""  # noqa: D402
        return isinstance(self.status, ActiveStatus)

    @property
    def ready_for_execution(self) -> bool:
        """Returns boolean indicating if Component is ready for execution.

        Extend this method with custom logic if this Component has validation to run before it can
        be executed.  For example:
        * a PebbleContainer can check whether the container is ready
        * a Component that requires leadership can check self._charm.unit.is_leader()
        """
        return True

    def remove(self, event):
        """Removes everything this Component should when handling a `remove` event."""
        pass

    @property
    def events_to_observe(self) -> List[BoundEvent]:
        """Returns the list of events this Component wants to observe."""
        return self._events_to_observe

    def _configure_app(self, event):
        """Execute everything this Component should do at the Application level.

        Generally, this should not need modification.  Instead, implement the Component's logic in
        one or more of:
        * _configure_unit: for work executed on every unit in an application
        * _configure_app_leader: for work executed on only the leader of an application
        * _configure_app_non_leader: for work executed on only the non-leaders of an application
        """
        if self._charm.unit.is_leader():
            self._configure_app_leader(event)
        else:
            self._configure_app_non_leader(event)

    # Methods that should be overridden when creating a Component subclass
    def _configure_unit(self, event):
        """Executes everything this Component should do for every Unit.

        Can be overridden to implement anything this Component should do for every unit in the
        charm.
        """
        pass

    def _configure_app_leader(self, event):
        """Execute everything this Component should do at the Application level for leaders.

        Can be overridden to implement anything this Component should do for the leader unit.
        """
        pass

    def _configure_app_non_leader(self, event):
        """Execute everything this Component should do at the Application level for non-Leaders.

        Can be overridden to implement anything this Component should do for every unit that is
        not the leader.
        """
        pass

    @abstractmethod
    def get_status(self) -> StatusBase:
        """Returns the status of this Component.

        Override this method to implement the logic that establishes your Component
        status (eg: if I have data from my relation, I am Active)
        """

    @property
    def status(self) -> StatusBase:
        """Returns the status of this Component."""
        return self.get_status()
