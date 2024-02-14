# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import functools
import logging
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple, Union

from jinja2 import Template
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError
from lightkube.core.resource import NamespacedResource, Resource, api_info
from ops.model import ActiveStatus, BlockedStatus

from ..exceptions import ErrorWithStatus
from ..lightkube.batch import apply_many, delete_many
from ..status_handling import get_first_worst_error
from ..types import LightkubeResourcesList, LightkubeResourceType, LightkubeResourceTypesSet
from ..types._charm_status import AnyCharmStatus
from ._check_resources import check_resources

ERROR_MESSAGE_NO_LABELS = "{caller} requires labels to be set"
ERROR_MESSAGE_NO_RESOURCE_TYPES = "{caller} requires labels to be defined"


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
        template_files: Optional[Iterable[Union[str, Path]]] = None,
        context: Optional[dict] = None,
        logger: Optional[logging.Logger] = None,
        labels: Optional[dict] = None,
        resource_types: LightkubeResourceTypesSet = None,
        lightkube_client: Client = None,
    ):
        """Returns a KubernetesResourceHandler instance.

        Args:
            field_manager (str): The name of the field manager to use when using server-side-apply
                           in kubernetes.  A good option for this is to use the application name
                           (eg: `self.model.app.name`).  If providing a `lightkube_client` arg,
                           this value will override that lightkube_client's field_manager.
            template_files (iterable): (Optional) An iterable of template file paths to
                                               render.  This is required to `render_manifests`, but
                                               can be left unset at instantiation and defined later
            context (dict): (Optional) A dict of context used to render the manifests.
                                               This is required to `render_manifests`, but can be
                                               left unset at instantiation and defined later.
            logger (logging.Logger): (Optional) A logger to use for logging (so that log messages
                                     emitted here will appear under the caller's log namespace).
                                     If not provided, a default logger will be created.
            labels (dict): (Optional) A dict of labels to use as a label selector for all resources
                           managed by this KRH.  These will be added to the rendered manifest at
                           .apply() time and will be used to find existing resources in
                           .get_deployed_resources().
                           Must be set to use .delete(), .reconcile(), or
                           .get_deployed_resources().
                           Recommended input for this is:
                             labels = {
                              'app.kubernetes.io/name': f"{self.model.app.name}-{self.model.name}",
                              'kubernetes-resource-handler-scope': 'some-user-chosen-scope'
                             }
                           See `get_default_labels` for a helper to generate this label dict.
            resource_types (set): (Optional) Set of Lightkube Resource objects that define the
                                   types of child resources managed by this KRH. Must be set to use
                                   .delete(), .reconcile(), or .get_deployed_resources().
            lightkube_client (lightkube.Client): (Optional) Lightkube Client to use for all k8s
                                                 operations.  If omitted, will create its own.
        """
        self._template_files = None
        self.template_files = template_files
        self._context = None
        self.context = context
        self._field_manager = field_manager
        self.resource_types = resource_types or set()
        self._labels = None
        self.labels = labels

        self._manifests = None

        if logger is None:
            self.log = logging.getLogger(__name__)  # TODO: Give default logger a better name
        else:
            self.log = logger

        self._lightkube_client = lightkube_client

    def compute_unit_status(self) -> AnyCharmStatus:
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

    def delete(self, ignore_missing=True):
        """Deletes all resources managed by this KubernetesResourceHandler.

        Requires that self.labels and self.resource_types be set.

        Args:
            ignore_missing: *(optional)* Avoid raising 404 errors on deletion (defaults to True)
        """
        _validate_labels_and_resource_types(self.labels, self.resource_types, caller_name="delete")

        resources_to_delete = self.get_deployed_resources()
        delete_many(self.lightkube_client, resources_to_delete, ignore_missing, self.log)

    def get_deployed_resources(self) -> LightkubeResourcesList:
        """Returns a list of all resources deployed by this KubernetesResourceHandler.

        Requires that self.labels and self.resource_types be set.

        This method will:
        * for each resource type included in self.resource_types
          * get all resources of that type in the Kubernetes cluster that match the label selector
            defined in self.labels

        Returns: A list of Lightkube Resource objects
        """
        _validate_labels_and_resource_types(
            self.labels, self.resource_types, caller_name="get_deployed_resources"
        )
        resources = []
        for resource_type in self.resource_types:
            if issubclass(resource_type, NamespacedResource):
                # Get resources from all namespaces
                namespace = "*"
            else:
                # Global resources have no namespace
                namespace = None
            resources.extend(
                self.lightkube_client.list(resource_type, namespace=namespace, labels=self._labels)
            )

        return resources

    def reconcile(self, force=False, ignore_missing=True):
        """Reconciles the managed resources, removing, updating, or creating objects as required.

        This method will:
        * compute a list of Lightkube Resources that are the "desired resources" (the state we
          want, given the current context
        * for each resource type in self.resource_types, get all resources currently deployed that
          match the label selector in self.labels
        * compare the current and desired resources, deleting any resources that exist but are not
          in the desired resource list
        * .apply() to update existing objects to the desired state and create new ones

        Args:
            force: *(optional)* Passed to self.apply().  This will force apply over any resources
                   marked as managed by another field manager.
            ignore_missing: *(optional)* Avoid raising 404 errors on deletion (defaults to True)
        """
        existing_resources = self.get_deployed_resources()
        desired_resources = self.render_manifests()

        # Delete any resources that exist but are no longer in scope
        resources_to_delete = _in_left_not_right(
            existing_resources, desired_resources, hasher=_hash_lightkube_resource
        )
        delete_many(self._lightkube_client, resources_to_delete, ignore_missing, self.log)

        # Update remaining resources and create any new ones
        self.apply(force=force)

    def render_manifests(
        self,
        template_files: Optional[Iterable[str]] = None,
        context: Optional[dict] = None,
        force_recompute: bool = False,
        create_resources_for_crds: bool = True,
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
            create_resources_for_crds (bool): If True, a generic resource will be created for
                                              every version of every CRD found that does not
                                              already have a generic resource.  There will be no
                                              side effect for any CRD that already has a generic
                                              resource.  Else if False, no generic resources.
                                              Default is True
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
        self._manifests = codecs.load_all_yaml(
            "\n---\n".join(manifest_parts), create_resources_for_crds=create_resources_for_crds
        )

        if self._labels is not None:
            _add_labels_to_resources(self._manifests, self._labels)

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

    def apply(self, force: bool = True):
        """Applies the managed Kubernetes resources, adding or modifying these objects.

        This can be invoked to create and/or update resources in the kubernetes cluster using
        Kubernetes server-side-apply.  The resources acted upon will be those returned by
        self.render_manifest().

        If self.labels is set, the labels will be added to all resources before applying them.

        If self.resource_types is set, the a ValueError will be raised if trying to create a
        resource not in the set.

        This function will only add or modify existing objects, it will not delete any resources.
        This includes cases where the manifests have changed over time.  For example:
            * If `render_manifests()` yields the list of resources [PodA], calling `.apply()`
              results in PodA being created
            * If later the charm state has changed and `render_manifests()` yields [PodB], calling
             `.apply()` results in PodB created and PodA being left unchanged (essentially
             orphaned)
        To simultaneously create, update, and delete resources, see self.reconcile().

        Args:
            force: *(optional)* Force is going to "force" apply requests. It means user will
                   re-acquire conflicting fields owned by other people.
        """
        resources = self.render_manifests(force_recompute=False)
        self.log.debug(f"Applying {len(resources)} resources")

        if self.labels is not None:
            resources = _add_labels_to_resources(resources, self.labels)

        if self.resource_types:
            try:
                _validate_resources(resources, allowed_resource_types=self.resource_types)
            except ValueError as e:
                raise ValueError(
                    "Failed to validate resources before applying them. This likely means we tried"
                    " to create a resource of type not included in `KRH.resource_types`."
                ) from e

        try:
            apply_many(
                client=self.lightkube_client,
                objs=resources,
                field_manager=self._field_manager,
                force=force,
                logger=self.log,
            )
        except ApiError as e:
            if e.status.code == 403:
                # Handle forbidden error as this likely means we do not have --trust
                self.log.error(
                    f"Received Forbidden (403) error from lightkube when creating resources: {e}"
                    " This may be due to the charm lacking permissions to create cluster-scoped"
                    " roles and resources. Charm must be deployed with `--trust`"
                )
                raise ErrorWithStatus(
                    "Cannot apply required resources. Charm may be missing `--trust`",
                    BlockedStatus,
                )
            elif self._check_and_report_k8s_conflict(e):
                # Conflict detected when applying K8s resources
                raise ErrorWithStatus(
                    "Cannot apply required resources: conflicts detected. Use with `force=True` to"
                    " force applying changes to the cluster",
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
    def labels(self):
        """Returns the dict of supplementary labels used for identifying these manifests."""
        return self._labels

    @labels.setter
    @auto_clear_manifests_cache
    def labels(self, value: dict):
        self._labels = value

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

    def _check_and_report_k8s_conflict(self, error) -> bool:
        """Return True if error status code is 409 (conflict), False otherwise."""
        if error.status.code == 409:
            self.logger.warning(f"Encountered a conflict: {error}")
            return True
        return False


def _add_label_field_to_resource(resource: LightkubeResourceType) -> LightkubeResourceType:
    """Adds a metadata.labels field to a Lightkube resource.

    Works around a bug where sometimes when the labels field is None it is not overwritable.
    Converts the object to a dict, adds the labels field, and then converts it back to the
    """
    as_dict = resource.to_dict()
    as_dict["metadata"]["labels"] = {}
    resource = resource.from_dict(as_dict)
    return resource


def _add_labels_to_resources(resources: LightkubeResourcesList, labels: dict):
    """Adds the given labels to every Lightkube resource in a list."""
    for i in range(len(resources)):
        if resources[i].metadata.labels is None:
            resources[i].metadata.labels = {}

        # Sometimes there is a bug where this field is not overwritable
        if resources[i].metadata.labels is None:
            resources[i] = _add_label_field_to_resource(resources[i])
        resources[i].metadata.labels.update(labels)
    return resources


def create_charm_default_labels(application_name: str, model_name: str, scope: str) -> dict:
    """Returns a default label style for the KubernetesResourceHandler label selector."""
    return {
        "app.kubernetes.io/instance": f"{application_name}-{model_name}",
        "kubernetes-resource-handler-scope": scope,
    }


def _get_resource_classes_in_manifests(
    resource_list: LightkubeResourcesList,
) -> LightkubeResourceTypesSet:
    """Returns a set of the resource classes in a list of resources."""
    return {type(rsc) for rsc in resource_list}


def _hash_lightkube_resource(resource: Resource) -> Tuple[str, str, str, str, str]:
    """Hashes a Lightkube Resource by returning a tuple of (group, version, kind, name, namespace).

    For global resources or resources without a namespace specified, namespace will be None.
    """
    resource_info = api_info(resource).resource

    return (
        resource_info.group,
        resource_info.version,
        resource_info.kind,
        resource.metadata.name,
        resource.metadata.namespace,
    )


def _in_left_not_right(left: list, right: list, hasher: Optional[Callable] = None) -> list:
    """Returns the items in left that are not right (the Set difference).

    Args:
        left: a list
        right: a list
        hasher: (Optional) a function that hashes the items in left and right to something
                immutable that can be compared.  If omitted, will use hash()

    Returns:
        A list of items in left that are not in right, based on the hasher function.
    """
    if hasher is None:
        hasher = hash

    left_as_dict = {hasher(resource): resource for resource in left}
    right_as_dict = {hasher(resource): resource for resource in right}

    keys_in_left_not_right = set(left_as_dict.keys()) - set(right_as_dict.keys())
    items_in_left_not_right = [left_as_dict[k] for k in keys_in_left_not_right]

    return items_in_left_not_right


def _validate_labels_and_resource_types(labels, resource_types, caller_name):
    """Validates labels and resource_types, raising a ValueError if either is empty."""
    if not labels:
        raise ValueError(ERROR_MESSAGE_NO_LABELS.format(caller=caller_name))
    if not resource_types:
        raise ValueError(ERROR_MESSAGE_NO_RESOURCE_TYPES.format(caller=caller_name))


def _validate_resources(resources, allowed_resource_types: LightkubeResourceTypesSet):
    """Validates that the resources are of a type in the allowed_resource_types set.

    Side effect: raises a ValueError if any resource is not in the allowed_resource_types set.

    Args:
        resources: a list of Lightkube resources to validate
        allowed_resource_types: a set of Lightkube resource classes to validate against
    """
    resource_types = _get_resource_classes_in_manifests(resources)
    for resource_type in resource_types:
        if resource_type not in allowed_resource_types:
            raise ValueError(
                f"Resource type {resource_type} not in allowed resource types"
                f" '{allowed_resource_types}'"
            )
