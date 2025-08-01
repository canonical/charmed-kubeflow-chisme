# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path
from typing import Literal, Optional, get_args
from unittest.mock import MagicMock, patch

from fixtures import (  # noqa F401
    clean_service_account_token_side_effects,
    harness_with_container,
)
from ops import ActiveStatus
from pytest import raises as pytest_raises

import charmed_kubeflow_chisme.components.sa_token_component
from charmed_kubeflow_chisme.components import SATokenComponent
from charmed_kubeflow_chisme.exceptions import GenericCharmRuntimeError

DUMMY_SA_TOKEN_DIR = Path(__file__).parent.parent.joinpath("data")
DUMMY_SA_TOKEN_FILENAME = DUMMY_SA_TOKEN_DIR / "dummy-sa-token"
LOGGING_METHODS = Literal["debug", "info", "warning", "error", "critical"]


def assert_no_classical_logging_method_ever_called(
    mocked_logger: MagicMock,
    exclude: Optional[LOGGING_METHODS] = None,
) -> bool:
    """Assert that none of the classical logging methods of the given mock were ever called, not
    even just one of them only once.
    """
    logging_methods_not_to_be_called = set(get_args(LOGGING_METHODS))
    if exclude is not None:
        logging_methods_not_to_be_called.remove(exclude)

    for loggin_method_name in logging_methods_not_to_be_called:
        exec(f"mocked_logger.{loggin_method_name}.assert_not_called()")


class TestSATokenComponent:
    audiences = ["whatever.audience.org"]
    container_name = "test-container"  # NOTE: hardcoded in "harness_with_container", keep as is
    expiration = 4294967296
    namespace = "whatever-namespace"
    service_account_name = "whatever-service-account"
    token_k8s_name = "whatever-sa-token-name"

    def test_previously_created_sa_token_available(self, harness_with_container):
        """Test that the previously created token file is available and that the status is set
        accordingly.
        """
        harness_with_container.set_can_connect(self.container_name, True)

        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=DUMMY_SA_TOKEN_FILENAME,
            path=DUMMY_SA_TOKEN_DIR,
            expiration=self.expiration,
        )

        # defining mock paths:
        base_patch_path = "charmed_kubeflow_chisme.components.sa_token_component"
        patch_path_for_k8s_client = f"{base_patch_path}.SATokenComponent.kubernetes_client"
        patch_path_for_logger = f"{base_patch_path}.logger"

        with patch(patch_path_for_k8s_client), patch(patch_path_for_logger) as mocked_logger:
            # ------------------------------------------------------------------------------------
            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # ------------------------------------------------------------------------------------
            # asserting expectations meet reality:

            assert isinstance(sa_token_component.status, ActiveStatus)
            assert_no_classical_logging_method_ever_called(mocked_logger)

    def test_sa_token_created_and_available_when_leader(
        self,
        harness_with_container,
        clean_service_account_token_side_effects
    ):
        """TODO
        """
        sa_token_dir = clean_service_account_token_side_effects
        sa_token_filename = "whatever-sa-token-filename"
        sa_token_content = "abcdefgh"

        harness_with_container.set_leader(True)
        harness_with_container.set_can_connect(self.container_name, True)

        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=sa_token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        # defining mock paths:
        base_patch_path = "charmed_kubeflow_chisme.components.sa_token_component"
        patch_path_for_k8s_client = f"{base_patch_path}.SATokenComponent.kubernetes_client"
        patch_path_for_logger = f"{base_patch_path}.logger"

        with patch(patch_path_for_k8s_client) as mocked_k8s_client,\
                patch(patch_path_for_logger) as mocked_logger:
            # ------------------------------------------------------------------------------------
            # defining mocked behaviors:

            (
                mocked_k8s_client.create_namespaced_service_account_token.return_value.status
                .token
            ) = sa_token_content

            # ------------------------------------------------------------------------------------
            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # ------------------------------------------------------------------------------------
            # asserting expectations meet reality:

            # charm status:
            assert isinstance(sa_token_component.status, ActiveStatus)

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, sa_token_filename)
            assert expected_sa_token_file_path.is_file()
            with open(expected_sa_token_file_path, "r") as file:
                assert sa_token_content == file.read()

            # logs:
            assert_no_classical_logging_method_ever_called(mocked_logger)

            # K8s API calls:
            mocked_k8s_client.create_namespaced_service_account_token.assert_called_once()
            kwargs = mocked_k8s_client.create_namespaced_service_account_token.call_args.kwargs
            assert kwargs["name"] == self.service_account_name
            assert kwargs["namespace"] == self.namespace
            spec = kwargs["body"].spec
            assert spec.audiences == self.audiences
            assert spec.expiration_seconds == self.expiration

    def test_sa_token_neither_created_nor_available_when_not_leader(
        self,
        harness_with_container,
        clean_service_account_token_side_effects
    ):
        """TODO
        """
        sa_token_dir = clean_service_account_token_side_effects
        sa_token_filename = "whatever-sa-token-filename"
        sa_token_content = "abcdefgh"

        harness_with_container.set_leader(False)
        harness_with_container.set_can_connect(self.container_name, True)

        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=sa_token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        # defining mock paths:
        base_patch_path = "charmed_kubeflow_chisme.components.sa_token_component"
        patch_path_for_k8s_client = f"{base_patch_path}.SATokenComponent.kubernetes_client"
        patch_path_for_logger = f"{base_patch_path}.logger"

        with patch(patch_path_for_k8s_client) as mocked_k8s_client,\
                patch(patch_path_for_logger) as mocked_logger:
            # ------------------------------------------------------------------------------------
            # defining mocked behaviors:

            (
                mocked_k8s_client.create_namespaced_service_account_token.return_value.status
                .token
            ) = sa_token_content

            # ------------------------------------------------------------------------------------
            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # ------------------------------------------------------------------------------------
            # asserting expectations meet reality:

            # charm status:
            with pytest_raises(GenericCharmRuntimeError) as error:
                sa_token_component.status
            assert error.value.msg == "The ServiceAccount token file is not present in the charm."

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, sa_token_filename)
            assert not expected_sa_token_file_path.exists()

            # logs:
            assert_no_classical_logging_method_ever_called(mocked_logger)

            # K8s API calls:
            mocked_k8s_client.create_namespaced_service_account_token.assert_not_called()
