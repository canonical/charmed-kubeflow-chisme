# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path
from typing import List, Union, Optional

import jinja2
from jinja2 import Environment, FileSystemLoader
from lightkube import Client, codecs
from lightkube.core.exceptions import ApiError
from lightkube.core.resource import NamespacedResource, GlobalResource
from ops.model import BlockedStatus

from . import exceptions


class KubernetesResourceHandlerInterface:
    """Defines an API for handling Kubernetes resources in the charm code."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.src_dir = Path("src")
        self.manifests_dir = self.src_dir / "manifests"

        # template_files are relative to the directory used by the jinva Environment.  By default,
        # this is the self.manifests_dir
        self.template_files = [
            "manifests.yaml.j2",
        ]

        # Properties
        self._jinja_env = None
        self._lightkube_client = None

    def reconcile(
        self,
        resources: Optional[List[Union[NamespacedResource, GlobalResource]]] = None,
    ):
        """Reconcile our Kubernetes objects to achieve the desired state

        This can be invoked to both install or update objects in the cluster.  It uses an apply
        logic to update things only if necessary and removes those that are no longer required.
        """
        self.log.info("Reconciling")
        if resources is None:
            resources = self.render_manifests()
        self.log.debug(f"Applying {len(resources)} resources")

        # TODO: implement check for difference in current vs desired
        current_resources = self.check_current_resources()
        if resources != current_resources:
            self.delete_unwanted_resources(resources, current_resources)

        try:
            # TODO: apply_many is a feature under development
            # let's be careful when using it as we cannot be sure
            # about it's current or future state. If it does not
            # get merged, we have to add more logic to this code.
            self.lightkube_client.apply_many(resources)
        except ApiError as e:
            # Handle fobidden error as this likely means we do not have --trust
            if e.status.code == 403:
                self.logger.error(
                    "Received Forbidden (403) error from lightkube when creating resources.  "
                    "This may be due to the charm lacking permissions to create cluster-scoped "
                    "roles and resources.  Charm must be deployed with `--trust`"
                )
                self.logger.error(f"Error received: {str(e)}")
                raise ReconcileError(
                    "Cannot create required resources.  Charm may be missing `--trust`",
                    BlockedStatus,
                )
            else:
                raise e
        self.log.info("Reconcile completed successfully")

    # TODO: implement these two methods
    def delete_unwanted_resources(self, desired, current):
        pass

    def check_current_resources(self):
        pass

    def render_manifests(self) -> List[Union[NamespacedResource, GlobalResource]]:
        """Renders this charm's manifests, returning them as a list of Lightkube Resources
        If overriding this class, you should replace it with a method that will always generate
        a list of all resources that should currently exist in the cluster.
        """
        # TODO: taking files from template_files might limit us
        # let's think how we can provide with a list of manifests
        self.log.info("Rendering manifests")
        self.log.debug(f"Rendering with context: {self.context_for_render}")
        manifest_parts = []
        for template_file in self.template_files:
            self.log.debug(f"Rendering manifest for {template_file}")
            template = self.jinja_env.get_template(template_file)
            rendered_template = template.render(**self.context_for_render)
            manifest_parts.append(rendered_template)
            self.log.debug(f"Rendered manifest:\n{manifest_parts[-1]}")
        return codecs.load_all_yaml("\n---\n".join(manifest_parts))

    def delete_resource(
        self, obj, namespace=None, ignore_not_found=False, ignore_unauthorized=False
    ):
        try:
            self.lightkube_client.delete(type(obj), obj.metadata.name, namespace=namespace)
        except ApiError as err:
            self.log.exception("ApiError encountered while attempting to delete resource.")
            if err.status.message is not None:
                if "not found" in err.status.message and ignore_not_found:
                    self.log.error(f"Ignoring not found error:\n{err.status.message}")
                elif "(Unauthorized)" in err.status.message and ignore_unauthorized:
                    # Ignore error from https://bugs.launchpad.net/juju/+bug/1941655
                    self.log.error(f"Ignoring unauthorized error:\n{err.status.message}")
                else:
                    self.log.error(err.status.message)
                    raise
            else:
                raise

    def generic_resources_handler(self):
        # TODO: define a way of handling generic resources,
        # how to create them, manage them, etc. This piece of
        # code does not have to live in this file/class.
        pass

    def remove(
        self,
        resource,
        namespace=None,
        ignore_not_found=False,
        ignore_unauthorized=False,
        labels=None,
    ):
        if labels is None:
            labels = {}
        for obj in self.lightkube_client.list(
            resource,
            labels={"app.juju.is/created-by": f"{self.app_name}"}.update(labels),
            namespace=namespace,
        ):
            self.delete_resource(
                obj,
                namespace=namespace,
                ignore_not_found=ignore_not_found,
                ignore_unauthorized=ignore_unauthorized,
            )

    @property
    def jinja_env(self) -> Environment:
        if self._jinja_env is None:
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(self.manifests_dir))
            )
        return self._jinja_env

    @jinja_env.setter
    def jinja_env(self, value: Environment):
        if isinstance(value, jinja2.Environment):
            self._jinja_env = value
        else:
            raise ValueError("jinja_env must be a jinja2.Environment")

    @property
    def lightkube_client(self) -> Client:
        if self._lightkube_client is None:
            self._lightkube_client = Client(field_manager=self.app_name)
        return self._lightkube_client

    @lightkube_client.setter
    def lightkube_client(self, value: Client):
        if isinstance(value, Client):
            self._lightkube_client = value
        else:
            raise ValueError("lightkube_client must be a lightkube.Client")

    @property
    def context_for_render(self):
        """Returns the context used for rendering the templates during self.render_manifest()

        The default methods of this base class will catch any ErrorWithStatus Exceptions raised
        here and cause the cahrm to enter that specified status.

        To replace the default context with your own, override this property to return your own
        custom context.  Or, to extend the default context, extend this method by overriding it
        and calling super().context_for_render() to inherrit the default context
        """
        return {
            "app_name": self.app_name,
            "model_name": self.model_name,
        }


class ReconcileError(exceptions.ErrorWithStatus):
    pass
