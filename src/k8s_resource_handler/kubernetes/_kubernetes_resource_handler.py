# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import functools
import logging
from pathlib import Path
from typing import Iterable, List, Optional

from jinja2 import Template
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError
from ops.model import ActiveStatus, BlockedStatus

from ..exceptions import ErrorWithStatus
from ..lightkube.batch import apply_many
from ..status_handling import get_first_worst_error
from ..types import CharmStatusType, LightkubeResourcesList
from ..types._charm_status import AnyCharmStatus
from ._check_resources import check_resources


def auto_clear_manifests_cache(func):
    """Decorates a class's method to delete any cached self._manifest after invocation.

    Useful for decorating properties which, when set, invalidate the existing cached manifest.
    """

    @functools.wraps(func)
    def decorated_f(self, *args, **kwargs):
        func(self, *args, **kwargs)

        # If we successfully get here, clear out existing cached manifests
        self._manifests = None

    return decorated_f


class KubernetesResourceHandler:
    """Defines an API for handling Kubernetes resources in charm code."""

    def __init__(
        self,
        field_manager: str,
        template_files: Optional[Iterable[str]] = None,
        context: Optional[dict] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Returns a KubernetesResourceHandler instance.

        Args:
            field_manager (str): The name of the field manager to use when using server-side-apply
                           in kubernetes.  A good option for this is to use the application name
                           (eg: `self.model.app.name`).
            template_files (iterable): (Optional) An iterable of template file paths to
                                               render.  This is required to `render_manifests`, but
                                               can be left unset at instantiation and defined later
            context (dict): (Optional) A dict of context used to render the manifests.
                                               This is required to `render_manifests`, but can be
                                               left unset at instantiation and defined later.
            logger (logging.Logger): (Optional) A logger to use for logging (so that log messages
                                     emitted here will appear under the caller's log namespace).
                                     If not provided, a default logger will be created.
        """
        self._template_files = None
        self.template_files = template_files
        self._context = None
        self.context = context
        self._field_manager = field_manager

        self._manifests = None

        if logger is None:
            self.log = logging.getLogger(__name__)  # TODO: Give default logger a better name
        else:
            self.log = logger

        self._lightkube_client = None

    def compute_unit_status(self) -> CharmStatusType:
        """Returns a suggested unit status given the state of the managed Kubernetes resources.

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

        The desired state used to make the assertions above is computed by using
        self.render_manifests(), and thus reflects the current template_files and context.

        TODO: This method will not notice that we have an extra resource (eg: if our
              render_manifests() previously output some Resource123, but now render_manifests()
              does not output that resource.
        TODO: This method directly logs errors to .log.  Is that a problem?  Maybe we should just
              return those errors?  Or could have a separate function that does that.

        Returns: A charm unit status (one of ActiveStatus, WaitingStatus, or BlockedStatus)
        """
        self.log.info("Computing a suggested unit status describing these Kubernetes resources")

        resources = self.render_manifests()
        resources_ok, errors = check_resources(self.lightkube_client, resources)
        suggested_unit_status = self._charm_status_given_resource_status(resources_ok, errors)

        self.log.debug(
            "Returning status describing Kubernetes resources state (note: this status "
            f"is not applied - that is the responsibility of the charm): {suggested_unit_status}"
        )
        return suggested_unit_status

    def reconcile(self):
        """To be implemented. This will reconcile resources, including deleting them."""
        raise NotImplementedError()

    def render_manifests(
        self,
        template_files: Optional[Iterable[str]] = None,
        context: Optional[dict] = None,
        force_recompute: bool = False,
    ) -> LightkubeResourcesList:
        """Renders this charm's manifests, returning them as a list of Lightkube Resources.

        This method requires that template_files and context both either passed as
        arguments or set in the KubernetesResourceHandler prior to calling.

        Args:
            template_files (iterable): (Optional) If provided, will replace existing value stored
                                       in self.template_files.
                                       This is a convenience provided to make the commonly used
                                       `self.context = context; self.render_manifests()` more
                                        convenient.
            context (dict): (Optional) If provided, will replace existing value stored in
                            self.context.  This is a convenience provided to make the commonly
                            used `self.context = context; self.render_manifests()` more convenient.
            force_recompute (bool): If true, will always recompute manifests even if cached
                                    manifests are available
        """
        self.log.info("Rendering manifests")

        # Update inputs
        if template_files is not None:
            self.template_files = template_files
        if context is not None:
            self.context = context

        # Return from cache if available
        if self._manifests is not None and force_recompute is False:
            return self._manifests

        # Assert that required inputs exist
        for attr in ["context", "template_files"]:
            attr_value = getattr(self, attr)
            if attr_value is None:
                raise ValueError(
                    f"render_manifests requires {attr} be defined" f" (got {attr}={attr_value})"
                )

        manifest_parts = self._render_manifest_parts()

        # Cache for later use
        self._manifests = codecs.load_all_yaml("\n---\n".join(manifest_parts))
        return self._manifests

    def _render_manifest_parts(self):
        """Private helper for rendering templates into manifests.

        Do not use directly - this does not validate inputs or cache results.

        Returns:
            A list of yaml strings of rendered templates
        """
        self.log.debug(f"Rendering with context: {self.context}")
        manifest_parts = []
        for template_file in self.template_files:
            self.log.debug(f"Rendering manifest for {template_file}")
            template = Template(Path(template_file).read_text())
            rendered_template = template.render(**self.context)
            manifest_parts.append(rendered_template)
            self.log.debug(f"Rendered manifest:\n{manifest_parts[-1]}")
        return manifest_parts

    def apply(self):
        """Applies the managed Kubernetes resources, adding or modifying these objects.

        This can be invoked to create and/or update resources in the kubernetes cluster using
        Kubernetes server-side-apply.  The resources acted upon will be those returned by
        self.render_manifest().

        This function will only add or modify existing objects, it will not delete any resources.
        This includes cases where the manifests have changed over time.  For example:
            * If `render_manifests()` yields the list of resources [PodA], calling `.apply()`
              results in PodA being created
            * If later the charm state has changed and `render_manifests()` yields [PodB], calling
             `.apply()` results in PodB created and PodA being left unchanged (essentially
             orphaned)
        """
        resources = self.render_manifests(force_recompute=False)
        self.log.debug(f"Applying {len(resources)} resources")

        try:
            apply_many(self.lightkube_client, resources)
        except ApiError as e:
            # Handle forbidden error as this likely means we do not have --trust
            if e.status.code == 403:
                self.log.error(
                    "Received Forbidden (403) error from lightkube when creating resources.  "
                    "This may be due to the charm lacking permissions to create cluster-scoped "
                    "roles and resources.  Charm must be deployed with `--trust`"
                )
                self.log.error(f"Error received: {str(e)}")
                raise ErrorWithStatus(
                    "Cannot apply required resources.  Charm may be missing `--trust`",
                    BlockedStatus,
                )
            else:
                raise e
        self.log.info("Reconcile completed successfully")

    @property
    def context(self):
        """Returns the dict context used for rendering manifests."""
        return self._context

    @context.setter
    @auto_clear_manifests_cache
    def context(self, value: dict):
        self._context = value

    @property
    def lightkube_client(self) -> Client:
        """Returns the Lightkube Client used by this instance.

        If uninitiated, will create, cache, and return a Client.
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

    @property
    def template_files(self):
        """Returns the list of template files used for rendering manifests."""
        return self._template_files

    @template_files.setter
    @auto_clear_manifests_cache
    def template_files(self, value: Iterable[str]):
        self._template_files = value

    def _charm_status_given_resource_status(
        self, resource_status: bool, errors: List[ErrorWithStatus]
    ) -> AnyCharmStatus:
        """Inspects resource status and errors, returning a suggested charm unit status."""
        if resource_status:
            return ActiveStatus()
        else:
            # Hit one or more errors with resources.  Return status for worst and log all
            self.log.info("One or more resources is not ready:")

            # Log all errors, ignoring None's
            errors = [error for error in errors if error is not None]
            for i, error in enumerate(errors, start=1):
                self.log.info(f"Resource issue {i}/{len(errors)}: {error.msg}")

        # Return status based on the worst thing we encountered
        return get_first_worst_error(errors).status
