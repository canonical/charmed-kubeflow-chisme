# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path
from typing import Optional, Callable, Iterable

from jinja2 import Template
from lightkube.core.exceptions import ApiError
from lightkube import codecs, Client
from ops.model import ActiveStatus, BlockedStatus

from .utils._check_resources import check_resources, get_first_worst_error
from .utils._reconcile_resources import reconcile_resources
from .exceptions import ReconcileError
from .types import LightkubeResourcesList


class KubernetesResourceHandler:
    """Defines an API for handling Kubernetes resources in charm code
    """

    def __init__(
        self,
        template_files_factory: Callable[[], Iterable[str]],
        context_factory: Callable[[], dict],
        field_manager: str,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Returns a KubernetesResourceHandler instance

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

    def render_manifests(self) -> LightkubeResourcesList:
        """Renders this charm's manifests, returning them as a list of Lightkube Resources"""
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

    def reconcile_resources(self, desired_resources):
        """Reconciles the desired state of the cluster wrt a list of k8s resources."""
        # TODO: implement
        try:
            resources = reconcile_resources(desired_resources)
        except SomeReconcileError:
            raise
        else:
            self.apply_changes_to_resources(resources)

    def get_resource_status(self, resources: Optional[LightkubeResourcesList] = None) -> CharmStatusType:
        """Computes the status of the managed resources as defined by the manifest
        The returned status is the worst status encountered, as defined in
        .lightkube.utilities.get_first_worst_error (blocked is worse than waiting, waiting is
        worse than active).  When multiple of the worst statuses are encountered, the first is
        returned.
        TODO: This method will not notice that we have an extra resource (eg: if our
              render_manifests() previously output some Resource123, but now render_manifests()
              does not output that resource.
        TODO: This method directly logs errors to .log.  Is that a problem?  Maybe we should just
              return those errors?  Or could have a separate function that does that.
        """
        self.log.info("Computing status")

        if resources is None:
            resources = self.render_manifests()

        charm_ok, errors = check_resources(self.lightkube_client, resources)
        if charm_ok:
            self.log.info("Status: active")
            status = ActiveStatus()
        else:
            # Hit one or more errors with resources.  Return status for worst and log all
            self.log.info("Charm is not active due to one or more issues:")

            # Log all errors, ignoring None's
            errors = [error for error in errors if error is not None]
            for i, error in enumerate(errors):
                self.log.info(f"Issue {i+1}/{len(errors)}: {error.msg}")

            # Return status based on the worst thing we encountered
            status = get_first_worst_error(errors).status

        return status
            
    def apply_changes_to_resources(self, resources: Optional[LightkubeResourcesList] = None):
        """Applies changes to Kubernetes objects.
        This can be invoked to both install or update objects in the cluster.  It uses an apply
        logic to update things only if necessary.
        """
        self.log.info("Rendering")
        if resources is None:
            resources = self.render_manifests()
        self.log.debug(f"Applying {len(resources)} resources")

        try:
            # TODO: This feature is not generally available in lightkube yet.  Should we make a
            #  helper here until it is?
            self.lightkube_client.apply_many(resources)
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
        if self._lightkube_client is None:
            self._lightkube_client = Client(field_manager=self._field_manager)
        return self._lightkube_client

    @lightkube_client.setter
    def lightkube_client(self, value: Client):
        if isinstance(value, Client):
            self._lightkube_client = value
        else:
            raise ValueError("lightkube_client must be a lightkube.Client")
