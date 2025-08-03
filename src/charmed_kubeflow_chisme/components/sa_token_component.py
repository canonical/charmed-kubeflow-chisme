#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Component for generating and managing the token of the given ServiceAccount."""

import logging
from pathlib import Path
from typing import List

from kubernetes.client import (
    ApiClient,
    AuthenticationV1TokenRequest,
    CoreV1Api,
    V1TokenRequestSpec,
)
from kubernetes.config import ConfigException, load_incluster_config, load_kube_config
from ops import ActiveStatus, StatusBase

from charmed_kubeflow_chisme.components.component import Component
from charmed_kubeflow_chisme.exceptions import GenericCharmRuntimeError

logger = logging.getLogger(__name__)


class SATokenComponent(Component):
    """Create and manage the given ServiceAccount token."""

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
            path (str): path of the directory where to store the ServiceAccount token file
            sa_name (str): ServiceAccount name
            sa_namespace (str): ServiceAccount namespace
        """
        super().__init__(*args, **kwargs)
        self._audiences = audiences
        self._expiration = expiration
        self._filename = filename
        self._sa_name = sa_name
        self._sa_namespace = sa_namespace
        self._dir_path = path

    @property
    def kubernetes_client(self) -> CoreV1Api:
        """Load the Kubernetes cluster configurations and return a CoreV1 Kubernetes client."""
        # accessing the K8s cluster configurations...
        try:
            # ...as processes running inside the cluster would:
            load_incluster_config()
        except ConfigException:
            # ...as processes external to the cluster would:
            load_kube_config()

        core_v1_api_client = CoreV1Api(ApiClient())
        return core_v1_api_client

    def _create_sa_token(self) -> AuthenticationV1TokenRequest:
        """Call the K8s API to generate the ServiceAccount token and return its response."""
        spec = V1TokenRequestSpec(audiences=self._audiences, expiration_seconds=self._expiration)
        body = AuthenticationV1TokenRequest(spec=spec)
        try:
            api_response = self.kubernetes_client.create_namespaced_service_account_token(
                name=self._sa_name, namespace=self._sa_namespace, body=body
            )
        except Exception as exc:
            logger.error(f"Request to create token for {self._sa_name} ServiceAccount failed.")
            raise exc
        return api_response

    def _generate_and_save_token(self, dir_path: str, filename: str) -> None:
        """Generate the ServiceAccount token and persist it to the given directory and filename.

        Args:
            dir_path (str): the path of the directory where to store the ServiceAccount token file
            filename (str): the filename for the ServiceAccount token file
        """
        if not Path(dir_path).is_dir():
            failure_message = (
                f"Token file for {self._sa_name} ServiceAccount cannot be created because path "
                "is not a directory."
            )
            logger.error(failure_message)
            raise RuntimeError(failure_message)

        if Path(dir_path, filename).is_file():
            logger.warning(
                f"Token file for {self._sa_name} ServiceAccount already exists, will be "
                "overridden."
            )

        token_creation_response = self._create_sa_token()
        token = token_creation_response.status.token

        with open(Path(dir_path, filename), "w") as token_file:
            token_file.write(token)

        logger.info(f"Token for {self._sa_name} ServiceAccount created and persisted.")

    def _configure_app_leader(self, event) -> None:
        """Generate and save a ServiceAccount token file.

        Raises:
            GenericCharmRuntimeError if the file could not be created.
        """
        try:
            self._generate_and_save_token(dir_path=self._dir_path, filename=self._filename)
        except Exception as exc:
            failure_message = (
                f"Token for {self._sa_name} ServiceAccount could not be created or persisted."
            )
            logger.error(failure_message)
            raise GenericCharmRuntimeError(failure_message) from exc

    def get_status(self) -> StatusBase:
        """Return ActiveStatus if the ServiceAccount token file is present or raise an exception.

        Raises:
            GenericCharmRuntimeError if the ServiceAccount token file is not present in the charm.
        """
        if not Path(self._dir_path, self._filename).is_file():
            failure_message = (
                f"Token file for {self._sa_name} ServiceAccount not present in charm."
            )
            logger.error(failure_message)
            raise GenericCharmRuntimeError(failure_message)
        return ActiveStatus()
