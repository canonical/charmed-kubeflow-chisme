# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""A reusable Component for Kubernetes resources."""
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

import lightkube
from lightkube.core.exceptions import ApiError
from lightkube.generic_resource import load_in_cluster_generic_resources
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase

from charmed_kubeflow_chisme.components.component import Component
from charmed_kubeflow_chisme.exceptions import GenericCharmRuntimeError
from charmed_kubeflow_chisme.kubernetes import KubernetesResourceHandler
from charmed_kubeflow_chisme.kubernetes._kubernetes_resource_handler import (
    _hash_lightkube_resource,
    _in_left_not_right,
)
from charmed_kubeflow_chisme.types import LightkubeResourceTypesSet


class KubernetesComponent(Component):
    """A reusable Component for Kubernetes resources."""

    def __init__(
        self,
        charm: CharmBase,
        name: str,
        resource_templates: Iterable[Union[str, Path]],
        krh_resource_types: LightkubeResourceTypesSet,
        krh_labels: dict,
        lightkube_client: lightkube.Client,
        context_callable: Optional[Callable] = None,
    ):
        super().__init__(charm=charm, name=name)
        self._charm = charm
        self._resource_templates = resource_templates
        self._krh_resource_types = krh_resource_types
        self._krh_labels = krh_labels
        self._lightkube_client = lightkube_client
        if context_callable is None:
            context_callable = lambda: {}  # noqa: E731
        self._context_callable = context_callable

    def _configure_app_leader(self, event):
        """Execute everything this Component should do at the Application level for leaders."""
        try:
            krh = self._get_kubernetes_resource_handler()
            krh.apply()
        except ApiError as e:
            # TODO: Blocked?
            raise GenericCharmRuntimeError("Failed to create Kubernetes resources") from e

    def _get_kubernetes_resource_handler(self) -> KubernetesResourceHandler:
        """Returns a KubernetesResourceHandler for this class."""
        k8s_resource_handler = KubernetesResourceHandler(
            # TODO: Make field_manager configurable?
            field_manager="lightkube",
            template_files=self._resource_templates,
            context=self._context_callable(),
            lightkube_client=self._lightkube_client,
            labels=self._krh_labels,
            resource_types=self._krh_resource_types,
        )
        load_in_cluster_generic_resources(k8s_resource_handler.lightkube_client)
        return k8s_resource_handler

    def _get_missing_kubernetes_resources(self):
        """Returns the desired resources this Component wants in Kubernetes but are not.

        TODO: Move this to the KRH class
        """
        krh = self._get_kubernetes_resource_handler()

        # TODO: Move this validation into KRH class
        existing_resources = krh.get_deployed_resources()
        desired_resources = krh.render_manifests()

        # Delete any resources that exist but are no longer in scope
        missing_resources = _in_left_not_right(
            desired_resources, existing_resources, hasher=_hash_lightkube_resource
        )
        return missing_resources

    def remove(self, event):
        """Removes all deployed resources."""
        krh = self._get_kubernetes_resource_handler()
        krh.delete()

    def get_status(self) -> StatusBase:
        """Returns the status of this Component based on whether its desired resources exist.

        Todo: This could use improvements on validation, and some of the logic could be moved into
         the KubernetesResourceHandler class.
        """
        if not self._charm.unit.is_leader():
            # We have no work to do, so we are always active.
            # Ideally, there would be a "no status" option.  Maybe Unknown?
            return ActiveStatus()

        # TODO: Add better validation
        missing_resources = self._get_missing_kubernetes_resources()

        # TODO: This feels awkward.  This will happen both if we haven't deployed anything yet (a
        #  typical case of "just wait longer") and if a resource has been lost.  How to handle this
        #  better?
        if len(missing_resources) > 0:
            return BlockedStatus(
                "Not all resources found in cluster.  This may be transient if we haven't tried "
                "to deploy them yet."
            )

        return ActiveStatus()
