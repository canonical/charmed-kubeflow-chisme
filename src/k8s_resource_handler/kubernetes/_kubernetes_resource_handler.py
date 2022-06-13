# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path
from typing import Callable, Iterable, Optional, List

from jinja2 import Template
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError
from ops.model import ActiveStatus, BlockedStatus

from ..exceptions import ReconcileError, ErrorWithStatus
from ..lightkube.batch import apply_many
from ..status_handling import get_first_worst_error
from ..types import CharmStatusType, LightkubeResourcesList
from ._check_resources import check_resources
from ..types._charm_status import AnyCharmStatus


class KubernetesResourceHandler:
    """Defines an API for handling Kubernetes resources in charm code."""

    def __init__(
        self,
        template_files_factory: Callable[[], Iterable[str]],
        context_factory: Callable[[], dict],
        field_manager: str,
        logger: Optional[logging.Logger] = None,
    ):
        """Returns a KubernetesResourceHandler instance.

        Args:
            template_files_factory (Callable): A callable that accepts no arguments and returns an
                                               iterable of template files to render
            context_factory: A callable that requires no arguments returns a dict of context for
                             rendering the templates
            field_manager: The name of the field manager to use when using server-side-apply in
                           kubernetes.  A good option for this is to use the application name
                           (eg: `self.model.app.name`).
            logger (logging.Logger): (Optional) A logger to use for logging (so that log messages
                                     emitted here will appear under the caller's log namespace).
                                     If not provided, a default logger will be created.
        """
        self._template_files_factory = template_files_factory
        self._context_factory = context_factory
        self._field_manager = field_manager

        if logger is None:
            self.log = logging.getLogger(__name__)  # TODO: Give default logger a better name
        else:
            self.log = logger

        self._lightkube_client = None

    def compute_unit_status(
        self, resources: Optional[LightkubeResourcesList] = None
    ) -> CharmStatusType:
        """Returns a suggested unit status given the state of the provided Kubernetes resources.

        The returned status is computed by mapping the state of each resource to a suggested unit
        status and then returning the worst status observed.  The statuses roughly map according
        to:
            ActiveStatus: All resources exist and are ready.  For example, a deployment exists and
                          has its owned pods also alive and ready.
            WaitingStatus: Resources are not ready yet, but are in a state that is expected to
                           proceed to ready/active without intervention.  For example, a deployment
                           exists but does not yet have its required pods.
            BlockedStatus: Resources are not ready and are not expected to proceed to a ready state
                           without intervention.  For example, a deployment should exist but does
                           not.

        TODO: This method will not notice that we have an extra resource (eg: if our
              render_manifests() previously output some Resource123, but now render_manifests()
              does not output that resource.
        TODO: This method directly logs errors to .log.  Is that a problem?  Maybe we should just
              return those errors?  Or could have a separate function that does that.

        Args:
            resources (list): (Optional) List of lightkube Resource objects defining kubernetes
                              resources.  If omitted, a list will be generated by calling
                              `self.render_manifest`.

        Returns: A charm unit status (one of ActiveStatus, WaitingStatus, or BlockedStatus)
        """
        self.log.info("Computing a suggested unit status describing these Kubernetes resources")

        if resources is None:
            resources = self.render_manifests()

        resources_ok, errors = check_resources(self.lightkube_client, resources)

        suggested_unit_status = self._charm_status_given_resource_status(resources_ok, errors)

        self.log.info(
            "Returning status describing Kubernetes resources state (note: this status "
            f"is not applied - that is the responsibility of the charm): {suggested_unit_status}"
        )
        return suggested_unit_status

    def reconcile(self, resources: Optional[LightkubeResourcesList] = None):
        """To be implemented. This will reconcile resources, including deleting them."""
        raise NotImplementedError()

    def render_manifests(self) -> LightkubeResourcesList:
        """Renders this charm's manifests, returning them as a list of Lightkube Resources."""
        self.log.info("Rendering manifests")
        context = self._context_factory()
        template_files = self._template_files_factory()

        self.log.debug(f"Rendering with context: {context}")
        manifest_parts = []
        for template_file in template_files:
            self.log.debug(f"Rendering manifest for {template_file}")
            template = Template(Path(template_file).read_text())
            rendered_template = template.render(**context)
            manifest_parts.append(rendered_template)
            self.log.debug(f"Rendered manifest:\n{manifest_parts[-1]}")
        return codecs.load_all_yaml("\n---\n".join(manifest_parts))

    def apply(self, resources: Optional[LightkubeResourcesList] = None):
        """Applies a list of Lightkube Kubernetes resources, adding or modifying these objects.

        This can be invoked to create and/or update resources in the kubernetes cluster using
        Kubernetes server-side-apply.  This action will only add or modify existing objects,
        it will not delete any resources, including in cases where the manifests have changed over
        time.  For example:
            * If `render_manifests()` yields the list of resources [PodA], calling `.apply()`
              results in PodA being created
            * If later the charm state has changed and `render_manifests()` yields [PodB], calling
             `.apply()` results in PodB created and PodA being left unchanged (essentially
             orphaned)
        """
        self.log.info("Applying")
        if resources is None:
            resources = self.render_manifests()
        self.log.debug(f"Applying {len(resources)} resources")

        try:
            apply_many(self.lightkube_client, resources, field_manager=self._field_manager)
        except ApiError as e:
            # Handle forbidden error as this likely means we do not have --trust
            if e.status.code == 403:
                self.log.error(
                    "Received Forbidden (403) error from lightkube when creating resources.  "
                    "This may be due to the charm lacking permissions to create cluster-scoped "
                    "roles and resources.  Charm must be deployed with `--trust`"
                )
                self.log.error(f"Error received: {str(e)}")
                raise ReconcileError(
                    "Cannot create required resources.  Charm may be missing `--trust`",
                    BlockedStatus,
                )
            else:
                raise e
        self.log.info("Reconcile completed successfully")

    @property
    def lightkube_client(self) -> Client:
        """Returns the Lightkube Client used by this instance.

        If uninitiated, will create, cache, and return a Client
        """
        if self._lightkube_client is None:
            self._lightkube_client = Client(field_manager=self._field_manager)
        return self._lightkube_client

    @lightkube_client.setter
    def lightkube_client(self, value: Client):
        """Stores a new Lightkube Client for this instance, replacing any previous one."""
        if isinstance(value, Client):
            self._lightkube_client = value
        else:
            raise ValueError("lightkube_client must be a lightkube.Client")

    def _charm_status_given_resource_status(
        self, resource_status: bool, errors: List[ErrorWithStatus]
    ) -> AnyCharmStatus:
        """Inspects resource status and errors, returning a suggested charm unit status"""
        if resource_status:
            return ActiveStatus()
        else:
            # Hit one or more errors with resources.  Return status for worst and log all
            self.log.info("One or more resources is not ready:")

            # Log all errors, ignoring None's
            errors = [error for error in errors if error is not None]
            for i, error in enumerate(errors):
                self.log.info(f"Resource issue {i+1}/{len(errors)}: {error.msg}")

        # Return status based on the worst thing we encountered
        return get_first_worst_error(errors).status