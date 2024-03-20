# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""Reusable Components for Pebble containers."""
import logging
from abc import abstractmethod
from pathlib import Path
from typing import Callable, List, Optional, Union

import jinja2
from ops import ActiveStatus, CharmBase, StatusBase, WaitingStatus
from ops.pebble import Layer, ServiceInfo

from charmed_kubeflow_chisme.components.component import Component

logger = logging.getLogger(__name__)


class LazyContainerFileTemplate:
    """A lazy file template renderer for use in pushing files to a Pebble container."""

    def __init__(
        self,
        destination_path: Union[Path, str],
        source_template_path: Optional[Union[Path, str, Callable[[], Union[Path, str]]]] = None,
        source_template: Optional[Union[str, Callable[[], str]]] = None,
        context: Optional[Union[dict, Callable[[], dict]]] = None,
        user: Optional[str] = None,
        group: Optional[str] = None,
        permissions: Optional[str] = None,
    ):
        """A lazy file template renderer for use in pushing files to a Pebble container.

        This generates a file from a template provided as a string or a file path.  The file will
        be rendered with a context provided as a dict.

        source_template_path, source_template, and context can also be provided as callables that
        return the appropriate value.  This allows for lazy evaluation of these values, which can
        be useful for using in charm Components.

        Args:
            destination_path: The path to the file in the container.
            source_template_path: The path to the source template file.
                                  Can be provided as a Path, str, or a function that returns
                                  either.
                                  Only one of source_template_path or source_template can be set.
            source_template: The source template string.
                             Can be provided as a str or a function that returns a str.
                             Only one of source_template_path or this can be set.
            context: A dict of context for rendering the file.  Leave this as None or {} if the
                     template does not need rendering.
                     Can be also be provided as a function returning a dict so the input can be
                     lazily evaluated.
            user: The user to own the file in the container.
            group: The group to own the file in the container.
            permissions: The permissions to set on the file in the container.
        """
        if source_template_path is not None and source_template is not None:
            raise ValueError("Only one of source_template_path or source_template can be set.")
        elif source_template_path is None and source_template is None:
            raise ValueError("One of source_template_path or source_template must be set.")

        self.destination_path = Path(destination_path)
        self._source_template_path = source_template_path
        self._source_template = source_template
        self._context = context
        self.user = user
        self.group = group
        self.permissions = permissions

    @property
    def context(self):
        """Returns the context_function input, rendered to a dict."""
        if callable(self._context):
            return self._context()
        return self._context or {}

    @property
    def source_template_path(self):
        """Returns the source_template_path input, rendered to a Path."""
        if callable(self._source_template_path):
            return Path(self._source_template_path())
        return Path(self._source_template_path)

    @property
    def source_template(self):
        """Returns the source_template input, rendered to a string."""
        if callable(self._source_template):
            return self._source_template()
        return self._source_template

    def get_inputs_for_push(self):
        """Returns a dict of the inputs expected by ops.model.Container.push()."""
        return dict(
            path=self.destination_path,
            source=self.render_source_template(),
            user=self.user,
            group=self.group,
            permissions=self.permissions,
            make_dirs=True,
        )

    def get_source_template(self):
        """Returns the source template, regardless of whether specified via path or string."""
        if self._source_template_path is not None:
            return self.source_template_path.read_text()
        else:
            return self.source_template

    def render_source_template(self):
        """Renders the source template with the given context, returning as a string."""
        source_template = self.get_source_template()
        template = jinja2.Template(source_template)
        rendered = template.render(**self.context)
        return rendered


class ContainerFileTemplate(LazyContainerFileTemplate):
    """A file template renderer for use in pushing files to a Pebble container."""

    def __init__(
        self,
        source_template_path: Union[Path, str, Callable[[], Union[Path, str]]],
        destination_path: Union[Path, str],
        context_function: Optional[Union[dict, Callable[[], dict]]] = None,
        user: Optional[str] = None,
        group: Optional[str] = None,
        permissions: Optional[str] = None,
    ):
        """Defines a file template that should be rendered and pushed into a Pebble container.

        This generates a file from a template provided as a file path.  The file will
        be rendered with a context provided as a dict.

        source_template_path and context_function can also be provided as callables that return the
        appropriate value.  This allows for lazy evaluation of these values, which can be useful
        for using in charm Components.

        This is a backwards-compatible refactor of the original ContainerFileTemplate using
        LazyContainerFileTemplate as the backend implementation.  This was introduced because
        ContainerFileTemplate had two required arguments, source_template_path and
        destination_path, whereas LazyContainerFileTemplate only requires destination_path.  This
        forced the order of the arguments to be changed, which is a breaking change in the API.

        Args:
            destination_path: The path to the file in the container.
            source_template_path: The path to the source template file.
                                  Can be provided as a Path, str, or a function that returns
                                  either.
                                  Only one of source_template_path or source_template can be set.
            context_function: A dict of context for rendering the file.  Leave this as None or {}
                              if the
                              template does not need rendering.
                              Can be also be provided as a function returning a dict so the input
                              can be lazily evaluated.
            user: The user to own the file in the container.
            group: The group to own the file in the container.
            permissions: The permissions to set on the file in the container.
        """
        if context_function is None:

            def context_function_():
                return {}

        elif not callable(context_function):

            def context_function_():
                return context_function

        else:
            context_function_ = context_function

        super().__init__(
            destination_path=destination_path,
            source_template_path=source_template_path,
            source_template=None,
            context=context_function_,
            user=user,
            group=group,
            permissions=permissions,
        )

    @property
    def context_function(self):
        """Returns the context_function input, unrendered.

        For backwards compatibility with previous versions of ContainerFileTemplate.
        """
        return self._context


class PebbleComponent(Component):
    """Wraps a non-service Pebble container."""

    def __init__(
        self,
        charm: CharmBase,
        name: str,
        container_name: str,
        *args,
        files_to_push: Optional[
            List[Union[ContainerFileTemplate, LazyContainerFileTemplate]]
        ] = None,
        **kwargs,
    ):
        """Instantiate the PebbleComponent.

        Args:
            charm: the charm using this PebbleComponent
            name: Name of this component
            container_name: Name of this container.  Note that this name is also used as the
                            parent object's Component.name parameter.
            files_to_push: Optional List of LazyContainerFileTemplate or ContainerFileTemplate
                           objects that define templates to be rendered and pushed into the
                           container as files
        """
        super().__init__(charm, name, *args, **kwargs)
        self.container_name = container_name
        # TODO: Should a PebbleComponent automatically be subscribed to this event?  Or just
        #  a PebbleServiceComponent?
        self._events_to_observe: List[str] = [
            get_pebble_ready_event_from_charm(self._charm, self.container_name)
        ]
        self._files_to_push = files_to_push or []

    @property
    def ready_for_execution(self) -> bool:
        """Returns True if Pebble is ready."""
        return self.pebble_ready

    @property
    def pebble_ready(self) -> bool:
        """Returns True if Pebble is ready."""
        return self._charm.unit.get_container(self.container_name).can_connect()

    def execute(self):
        """Execute the given command in the container managed by this Component."""
        raise NotImplementedError()

    def _push_files_to_container(self):
        """Renders and pushes the files defined in self._files_to_push into the container."""
        container = self._charm.unit.get_container(self.container_name)
        for container_file_template in self._files_to_push:
            container.push(**container_file_template.get_inputs_for_push())

    def get_status(self) -> StatusBase:
        """Returns the status of this Component."""
        if not self.pebble_ready:
            return WaitingStatus("Waiting for Pebble to be ready.")

        return ActiveStatus()


class PebbleServiceComponent(PebbleComponent):
    """Wraps a Pebble container that implements one or more services."""

    def __init__(self, *args, service_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = service_name

    def _configure_unit(self, event):
        """Executes everything this Component should do for every Unit."""
        # TODO: Need to call super()._configure_unit()?
        super()._configure_unit(event)
        # TODO: Checks for if we are the leader/there is a leader?  or skip that?
        # TODO: This may need refinement.  Sunbeam does it differently from us.  Why?  Maybe they
        #  dont expect to ever update and existing pebble plan?
        if not self.pebble_ready:
            logging.info(f"Container {self.container_name} not ready - cannot configure unit.")
            return

        # TODO: Detect file changes and trigger a replan on any file change too?
        self._push_files_to_container()
        self._update_layer()

    def _update_layer(self):
        """Updates the Pebble layer for this component, re-planning the services afterward."""
        container = self._charm.unit.get_container(self.container_name)
        new_layer = self.get_layer()

        current_layer = container.get_plan()
        if current_layer.services != new_layer.services:
            container.add_layer(self.container_name, new_layer, combine=True)
            # TODO: Add error handling here?  Not sure what will catch them yet so left out for now
            container.replan()

    @abstractmethod
    def get_layer(self) -> Layer:
        """Pebble configuration layer for the container.

        Override this method with your own layer configuration.
        """

    @property
    def service_ready(self) -> bool:
        """Returns True if all services provided by this container are running."""
        if not self.pebble_ready:
            return False
        return len(self.get_services_not_active()) == 0

    def get_services_not_active(self) -> List[ServiceInfo]:
        """Returns a list of Pebble services that are defined in get_layer but not active."""
        # Get the expected services by inspecting our layer specification
        services_expected = [
            ServiceInfo(service_name, "disabled", "inactive")
            for service_name in self.get_layer().services.keys()
        ]
        if not self.pebble_ready:
            return services_expected

        container = self._charm.unit.get_container(self.container_name)
        services = container.get_services()

        # Get any services that should be active, but are not in the container at all
        services_not_found = [
            service for service in services_expected if service.name not in services.keys()
        ]
        services_not_active = [
            service for service in services.values() if not service.is_running()
        ]

        services_not_ready = services_not_found + services_not_active

        return services_not_ready

    def get_status(self) -> StatusBase:
        """Returns the status of this Pebble service container.

        Status is determined by checking whether the container and service are up.
        """
        # TODO: Report on checks in the Status?
        if not self.pebble_ready:
            return WaitingStatus("Waiting for Pebble to be ready.")
        services_not_ready = self.get_services_not_active()
        if len(services_not_ready) > 0:
            service_names = ", ".join([service.name for service in services_not_ready])
            return WaitingStatus(
                f"Waiting for Pebble services ({service_names}).  If this persists, it could be a"
                f" blocking configuration error."
            )
        return ActiveStatus()


def get_pebble_ready_event_from_charm(charm: CharmBase, container_name: str) -> str:
    """Returns the pebble-ready event for a given container_name."""
    prefix = container_name.replace("-", "_")
    event_name = f"{prefix}_pebble_ready"
    return getattr(charm.on, event_name)
