# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""A reusable reconcile loop for Charms."""
import logging
from typing import List, Optional, Tuple

from ops import ActiveStatus, CharmBase, EventBase, MaintenanceStatus, Object, StatusBase

from ..status_handling.multistatus import add_prefix_to_status
from .component import Component
from .component_graph import ComponentGraph
from .component_graph_item import ComponentGraphItem

logger = logging.getLogger(__name__)


class CharmReconciler(Object):
    """A reusable reconcile loop for Charms."""

    def __init__(
        self,
        charm: CharmBase,
        component_graph: Optional[ComponentGraph] = None,
        reconcile_on_update_status: bool = True,
    ):
        """A reusable reconcile loop for Charms.

        TODO: Do we really need to pass `charm` here?  We barely use it.  I think we need it (or
         really, the framework) to

        Args:
            charm: a CharmBase object to operate from this CharmReconciler
            component_graph: (optional) a ComponentGraph that is used to define the execution order
                             of Components.  If None, an empty ComponentGraph will be created.
            reconcile_on_update_status: If True, will do a full execution loop on the update-status
                                        event.  Else, will only assess the status of all Components
                                        without executing any.
        """
        super().__init__(parent=charm, key=None)

        if component_graph is None:
            component_graph = ComponentGraph()

        self._charm = charm
        self._component_graph = component_graph
        self._reconcile_on_update_status = reconcile_on_update_status
        # Indicates whether `.install()` has been called before
        self._installed = False

    def add(
        self,
        component: Component,
        depends_on: Optional[List[ComponentGraphItem]] = None,
    ) -> ComponentGraphItem:
        """Add a component to the graph, returning a ComponentGraphItem for this Component.

        Note that calling .add() after .install() raises a RuntimeError.  This is because
        Components can request we observe custom events, so .install() should be the last step
        in setting up the CharmReconciler.

        Args:
            component: the Component to add to this execution graph
            depends_on: the list of registered ComponentGraphItems that this Component depends on
                        being Active before it should run.
        """
        if self._installed:
            raise RuntimeError(
                "Cannot .add() a Component after `CharmReconciler.install()` has been called"
            )
        return self._component_graph.add(component, depends_on)

    def reconcile(self, event: EventBase):
        """Executes all components that are ready for execution, ordered by their dependencies."""
        logger.info(f"Starting `execute_components` for event '{event.handle}'")

        # Set all .executed=False, just in case this is not a fresh init of the Charm.
        # This is to protect against https://github.com/canonical/operator/issues/736 and
        # how custom events also don't reinit the charm (discussed in
        # https://github.com/canonical/operator/issues/952)
        for component_graph_item in self._component_graph.component_items.values():
            component_graph_item.executed = False

        # TODO: Think this through again.  Look ok still?
        for component_item in self._component_graph.yield_executable_component_items():
            logger.info(f"Executing component: '{component_item.name}'")
            self._charm.unit.status = MaintenanceStatus(
                f"Reconciling charm: executing component {component_item.name}"
            )

            # Execute the component and log any errors
            try:
                component_item.component.configure_charm(event)
                logger.info(
                    f"Execution for component '{component_item.name}' complete.  Component now has "
                    f"status '{component_item.component.get_status()}'"
                )
            except Exception as err:
                _ = err  # Suppress the lint about broad exceptions
                msg = (
                    f"execute_components caught unhandled exception when executing "
                    f"configure_charm for {component_item.name}"
                )
                logger.error(msg, exc_info=True)

        logger.info("execute_components execution loop complete.")
        self._update_charm_status()

    def install_default_event_handlers(
        self,
    ):
        """Installs event handlers on the default list of charm events.

        Attaches the `reconcile` handler for the following charm events:
        * install
        * config_changed
        * leader_elected
        * leader_settings_changed
        * any other event that is specified by a Component via Component.events_to_observe,
          for example a pebble-ready or relation event

        Attaches the `remove` handler for the following charm events:
        * remove

        Attaches the `update_status` handler for the following charm events:
        * update-status
        """
        # Used as a guard against installing twice or .add()ing Components after calling this
        # method.
        if self._installed:
            raise RuntimeError(
                "CharmReconciler tried to install event handlers more than once.  To avoid "
                "duplicate event handling, event handlers can only be installed once."
            )
        self._installed = True

        # Handle all default Charm reconciliation events
        self._charm.framework.observe(self._charm.on.install, self.reconcile)
        self._charm.framework.observe(self._charm.on.config_changed, self.reconcile)
        self._charm.framework.observe(self._charm.on.leader_elected, self.reconcile)
        self._charm.framework.observe(self._charm.on.leader_settings_changed, self.reconcile)
        # Handle any additional events requested by our Components
        additional_events = self._component_graph.get_events_to_observe()
        for event in additional_events:
            self._charm.framework.observe(event, self.reconcile)

        self._charm.framework.observe(self._charm.on.remove, self.remove)

        self._charm.framework.observe(self._charm.on.update_status, self.update_status)

    def remove(self, event: EventBase):
        """Runs Component.remove for all components.

        Note: unlike execute_components(), the order of in which Components are .remove()'ed
              is not guaranteed.
        """
        for component_item in self._component_graph.component_items.values():
            try:
                component_item.component.remove(event)
                logger.info(f"Successfully removed component {component_item.name}")
            except Exception as err:
                _ = err  # Suppress the lint about broad exceptions
                logger.warning(f"Failed to remove component {component_item.name}", exc_info=True)

    def status(self) -> StatusBase:
        """Returns a status representing the entire charm execution.

        .install() would attach this to the update-status event.

        Status is assembled from the .status of the Components.  If A and B are
        Active, then this is Active.

        This probably needs context from the dependencies between the Components
        (B is blocked by A).  Could leverage something like the
        Prioritiser class.  This status needs to be passed along somehow to the
        charm's overall status.
        """
        raise NotImplementedError()

    def update_status(self, event: EventBase):
        """Handler for an update-status event.  Updates charm with the aggregate status.

        Optionally executes the Components before updating status, as defined by
        self._reconcile_on_update_status.
        """
        if self._reconcile_on_update_status:
            logger.info(
                f"CharmReconciler.update_status executing full charm reconcile because"
                f"reconcile_on_update_status={self._reconcile_on_update_status}"
            )
            return self.reconcile(event)
        else:
            logger.info(
                f"CharmReconciler.update_status updating Component statuses without a full charm"
                f"reconcile because reconcile_on_update_status={self._reconcile_on_update_status}"
            )
            # Set all component_items to executed so they report status as if execution is
            # complete.
            for component_item in self._component_graph.component_items.values():
                component_item.executed = True
            return self._update_charm_status()

    def _get_component_statuses(self) -> List[Tuple[str, StatusBase]]:
        """Returns all charm Component Statuses as a list."""
        return self._component_graph.status_prioritiser.all()

    def _update_charm_status(self):
        """Computes Component statuses, updating the attached Charm's with the aggregate status.

        Also logs the full status details to the charm logs.

        By default, if this CharmReconciler has no components then it is active.
        """
        statuses = self._get_component_statuses()
        if len(self._component_graph) == 0:
            # If we have nothing to be inactive, we are active.
            self._charm.unit.status = ActiveStatus()
            return

        log_component_statuses(statuses, logger)

        # Set the charm status to the worst of all statuses
        status = self._component_graph.status_prioritiser.highest(statuses)
        logger.info(f"Status of unit set to: {status}")
        self._charm.unit.status = status


def log_component_statuses(statuses: List[Tuple[str, StatusBase]], logger: logging.Logger):
    """Logs the status of all components in a CharmReconciler."""
    logger.info("Status of all CharmReconciler Components:")
    for name, status in statuses:
        logger.info(f"Status: {add_prefix_to_status(name, status)}")
