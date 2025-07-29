#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Component for generating and managing a given ServiceAccount token."""

import logging
from pathlib import Path
from typing import List

import kubernetes
from charmed_kubeflow_chisme.components.component import Component
from charmed_kubeflow_chisme.exceptions import GenericCharmRuntimeError
from kubernetes.client import AuthenticationV1TokenRequest, CoreV1Api, V1TokenRequestSpec
from kubernetes.client.rest import ApiException
from kubernetes.config import ConfigException
from ops import ActiveStatus, StatusBase

logger = logging.getLogger(__name__)


class SATokenComponent(Component):
    """Create and manage a given ServiceAccount token."""

    def __init__(
        self,
        *args,
        audiences: List[str],
        sa_name: str,
        sa_namespace: str,
        path: str,
        filename: str,
        expiration: int,
        **kwargs,
    ):
        """Instantiate the SATokenComponent.

        Args:
            audiences (List[str]): list of audiences for the ServiceAccount token
            expiration (int): ServiceAccount token expiration time in seconds
            filename (str): filename for the ServiceAccount token file
            path (str): the path of the directory where to store the ServiceAccount token file
            sa_name (str): ServiceAccount name
            sa_namespace (str): ServiceAccount namespace
        """
        super().__init__(*args, **kwargs)
        self._audiences = audiences
        self._expiration = expiration
        self._filename = filename
        self._sa_name = sa_name
        self._sa_namespace = sa_namespace
        self._path = path

    @property
    def kubernetes_client(self) -> CoreV1Api:
        """Load the cluster configurations and return a CoreV1 Kubernetes client."""
        try:
            kubernetes.config.load_incluster_config()
        except ConfigException:
            kubernetes.config.load_kube_config()

        api_client = kubernetes.client.ApiClient()
        core_v1_api = kubernetes.client.CoreV1Api(api_client)
        return core_v1_api

    def _create_sa_token(self) -> AuthenticationV1TokenRequest:
        """Return a TokenRequest response."""
        spec = V1TokenRequestSpec(audiences=self._audiences, expiration_seconds=self._expiration)
        body = kubernetes.client.AuthenticationV1TokenRequest(spec=spec)
        try:
            api_response = self.kubernetes_client.create_namespaced_service_account_token(
                name=self._sa_name, namespace=self._sa_namespace, body=body
            )
        except ApiException as e:
            logger.error("Error creating the ServiceAccount token.")
            raise e
        return api_response

    def _generate_and_save_token(self, path: str, filename: str) -> None:
        """Generate a ServiceAccount token and save it with the given filename to the given
        folder path inside the charm container.

        Args:
            path (str): the path of the directory where to store the ServiceAccount token file
            filename (str): the filename for the ServiceAccount token file
        """
        if not Path(path).is_dir():
            failure_message = (
                "The path does not exist, so the ServiceAccount token file cannot be saved."
            )
            logger.error(failure_message)
            raise RuntimeError(failure_message)
        if Path(path, filename).is_file():
            logger.info(
                "The ServiceAccount token file already exists, nothing else to do."
            )
        api_response = self._create_sa_token()
        token = api_response.status.token
        with open(Path(path, filename), "w") as token_file:
            token_file.write(token)

    def _configure_app_leader(self, event) -> None:
        """Generate and save a ServiceAccount token file.

        Raises:
            GenericCharmRuntimeError if the file could not be created.
        """
        try:
            self._generate_and_save_token(self._path, self._filename)
        except (RuntimeError, ApiException) as exc:
            raise GenericCharmRuntimeError(
                "Failed to create and save a ServiceAccount token."
            ) from exc

    def get_status(self) -> StatusBase:
        """Return ActiveStatus if the ServiceAccount token file is present.

        Raises:
            GenericCharmRuntimeError if the ServiceAccount token file is not present in the charm.
        """
        if not Path(self._path, self._filename).is_file():
            raise GenericCharmRuntimeError(
                "The ServiceAccount token file is not present in charm."
            )
        return ActiveStatus()
