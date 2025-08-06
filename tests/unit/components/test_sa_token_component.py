# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path
from unittest.mock import patch

from fixtures import (  # noqa F401
    clean_service_account_token_test_directory,
    harness_with_container,
)
from ops import ActiveStatus
from pytest import mark
from pytest import raises as pytest_raises

from charmed_kubeflow_chisme.components import SATokenComponent
from charmed_kubeflow_chisme.components.sa_token_component import CoreV1Api
from charmed_kubeflow_chisme.exceptions import GenericCharmRuntimeError

K8S_CLIENT_CREATE_TOKEN_API = "create_namespaced_service_account_token"
K8S_CLIENT_LOAD_CONFIG_PATH = (
    "charmed_kubeflow_chisme.components.sa_token_component.load_incluster_config"
)
PRECREATED_SA_TOKEN_DIR = Path(__file__).parent.parent.joinpath("data")
PRECREATED_SA_TOKEN_FILENAME = PRECREATED_SA_TOKEN_DIR / "precreated-sa-token"


class TestSATokenComponent:
    audiences = ["whatever.audience.org"]
    container_name = "test-container"  # NOTE: hardcoded in "harness_with_container", keep as is
    expiration = 4294967296
    namespace = "whatever-namespace"
    service_account_name = "whatever-service-account"
    token_content = "abcdefgh"
    token_filename = "sa-token-filename"
    token_k8s_name = "whatever-sa-token-name"

    def test_sa_token_created_and_available_when_leader(
        self, harness_with_container, clean_service_account_token_test_directory
    ):
        """Check the token is correctly generated and saved when the unit is leader."""
        sa_token_dir = clean_service_account_token_test_directory

        harness_with_container.set_leader(True)

        harness_with_container.set_can_connect(self.container_name, True)
        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=self.token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        with (
            patch(K8S_CLIENT_LOAD_CONFIG_PATH),
            patch.object(CoreV1Api, K8S_CLIENT_CREATE_TOKEN_API) as mocked_k8s_client_create_token,
        ):
            # defining mocked behaviors:

            mocked_k8s_client_create_token.return_value.status.token = self.token_content

            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # asserting expectations meet reality:

            # charm status:
            assert isinstance(sa_token_component.status, ActiveStatus)

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, self.token_filename)
            assert expected_sa_token_file_path.is_file()
            with open(expected_sa_token_file_path, "r") as file:
                assert file.read() == self.token_content

            # K8s API calls:
            mocked_k8s_client_create_token.assert_called_once()
            kwargs = mocked_k8s_client_create_token.call_args.kwargs
            assert kwargs["name"] == self.service_account_name
            assert kwargs["namespace"] == self.namespace
            spec = kwargs["body"].spec
            assert spec.audiences == self.audiences
            assert spec.expiration_seconds == self.expiration

    def test_sa_token_not_created_when_not_leader(
        self, harness_with_container, clean_service_account_token_test_directory
    ):
        """Check the token is not generated when the unit is not leader."""
        sa_token_dir = clean_service_account_token_test_directory

        harness_with_container.set_leader(False)

        harness_with_container.set_can_connect(self.container_name, True)
        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=self.token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        with (
            patch(K8S_CLIENT_LOAD_CONFIG_PATH),
            patch.object(CoreV1Api, K8S_CLIENT_CREATE_TOKEN_API) as mocked_k8s_client_create_token,
        ):
            # defining mocked behaviors:

            mocked_k8s_client_create_token.return_value.status.token = self.token_content

            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # asserting expectations meet reality:

            # charm status:
            with pytest_raises(GenericCharmRuntimeError) as error:
                sa_token_component.status
            assert error.value.msg == (
                f"Token file for {self.service_account_name} ServiceAccount not present in charm."
            )

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, self.token_filename)
            assert not expected_sa_token_file_path.exists()

            # K8s API calls:
            mocked_k8s_client_create_token.assert_not_called()

    def test_failing_k8s_api_handled_when_leader(
        self, harness_with_container, clean_service_account_token_test_directory
    ):
        """Check the token is not generated when the unit is leader but the K8s API fails."""
        sa_token_dir = clean_service_account_token_test_directory

        harness_with_container.set_leader(True)

        harness_with_container.set_can_connect(self.container_name, True)
        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=self.token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        with (
            patch(K8S_CLIENT_LOAD_CONFIG_PATH),
            patch.object(CoreV1Api, K8S_CLIENT_CREATE_TOKEN_API) as mocked_k8s_client_create_token,
        ):
            # defining mocked behaviors:

            mocked_k8s_client_create_token.side_effect = Exception(
                "K8s API call to generate token failed."
            )

            # executing the charm logic:

            with pytest_raises(GenericCharmRuntimeError) as error:
                sa_token_component.configure_charm("mocked event")

            # asserting expectations meet reality:

            # charm status:
            assert error.value.msg == (
                f"Token for {self.service_account_name} ServiceAccount could not be created or "
                "persisted."
            )
            with pytest_raises(GenericCharmRuntimeError) as error:
                sa_token_component.status
            assert error.value.msg == (
                f"Token file for {self.service_account_name} ServiceAccount not present in charm."
            )

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, self.token_filename)
            assert not expected_sa_token_file_path.exists()

            # K8s API calls:
            mocked_k8s_client_create_token.assert_called_once()
            kwargs = mocked_k8s_client_create_token.call_args.kwargs
            assert kwargs["name"] == self.service_account_name
            assert kwargs["namespace"] == self.namespace
            spec = kwargs["body"].spec
            assert spec.audiences == self.audiences
            assert spec.expiration_seconds == self.expiration

    def test_failing_k8s_api_irrelevant_when_not_leader(
        self, harness_with_container, clean_service_account_token_test_directory
    ):
        """Check the token is not generated when the unit is not leader and the K8s API fails."""
        sa_token_dir = clean_service_account_token_test_directory

        harness_with_container.set_leader(False)

        harness_with_container.set_can_connect(self.container_name, True)
        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=self.token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        with (
            patch(K8S_CLIENT_LOAD_CONFIG_PATH),
            patch.object(CoreV1Api, K8S_CLIENT_CREATE_TOKEN_API) as mocked_k8s_client_create_token,
        ):
            # defining mocked behaviors:

            mocked_k8s_client_create_token.side_effect = Exception(
                "K8s API call to generate token failed."
            )

            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # asserting expectations meet reality:

            # charm status:
            with pytest_raises(GenericCharmRuntimeError) as error:
                sa_token_component.status
            assert error.value.msg == (
                f"Token file for {self.service_account_name} ServiceAccount not present in charm."
            )

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, self.token_filename)
            assert not expected_sa_token_file_path.exists()

            # K8s API calls:
            mocked_k8s_client_create_token.assert_not_called()

    @mark.parametrize("is_leader", (False, True))
    def test_previously_created_sa_token_recognized(self, harness_with_container, is_leader):
        """Check the previously created token file is recognized."""
        harness_with_container.set_leader(is_leader)

        harness_with_container.set_can_connect(self.container_name, True)
        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=PRECREATED_SA_TOKEN_FILENAME,
            path=PRECREATED_SA_TOKEN_DIR,
            expiration=self.expiration,
        )

        # executing the charm logic:

        # NOTE: purposely not triggering events to avoid recreating the token when leader

        # asserting expectations meet reality:

        # charm status:
        assert isinstance(sa_token_component.status, ActiveStatus)

    def test_previously_created_sa_token_recreated_when_leader(
        self, harness_with_container, clean_service_account_token_test_directory
    ):
        """Check the previously created token file is recreated and overridden when leader."""
        sa_token_dir = clean_service_account_token_test_directory
        first_token_content = self.token_content
        second_token_content = f"{self.token_content}-xyz"

        harness_with_container.set_leader(True)

        harness_with_container.set_can_connect(self.container_name, True)
        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=self.token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        with (
            patch(K8S_CLIENT_LOAD_CONFIG_PATH),
            patch.object(CoreV1Api, K8S_CLIENT_CREATE_TOKEN_API) as mocked_k8s_client_create_token,
        ):
            # first-time token creation

            # defining mocked behaviors:

            mocked_k8s_client_create_token.return_value.status.token = first_token_content

            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # asserting expectations meet reality:

            # charm status:
            assert isinstance(sa_token_component.status, ActiveStatus)

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, self.token_filename)
            assert expected_sa_token_file_path.is_file()
            with open(expected_sa_token_file_path, "r") as file:
                assert file.read() == first_token_content

            # K8s API calls:
            mocked_k8s_client_create_token.assert_called_once()
            kwargs = mocked_k8s_client_create_token.call_args.kwargs
            assert kwargs["name"] == self.service_account_name
            assert kwargs["namespace"] == self.namespace
            spec = kwargs["body"].spec
            assert spec.audiences == self.audiences
            assert spec.expiration_seconds == self.expiration

            # token recreation

            # defining mocked behaviors:

            mocked_k8s_client_create_token.return_value.status.token = second_token_content

            # executing the charm logic:

            sa_token_component.configure_charm("mocked event")

            # asserting expectations meet reality:

            # charm status:
            assert isinstance(sa_token_component.status, ActiveStatus)

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, self.token_filename)
            assert expected_sa_token_file_path.is_file()
            with open(expected_sa_token_file_path, "r") as file:
                assert file.read() == second_token_content

            # K8s API calls:
            assert mocked_k8s_client_create_token.call_count == 2
            kwargs = mocked_k8s_client_create_token.call_args.kwargs
            assert kwargs["name"] == self.service_account_name
            assert kwargs["namespace"] == self.namespace
            spec = kwargs["body"].spec
            assert spec.audiences == self.audiences
            assert spec.expiration_seconds == self.expiration

    def test_sa_token_not_created_when_leader_but_dir_path_does_not_exist(
        self, harness_with_container, clean_service_account_token_test_directory
    ):
        """Check the previously created token file is recognized."""
        sa_token_dir = (
            clean_service_account_token_test_directory / "subdirectoty-that-does-not-exist"
        )

        harness_with_container.set_leader(True)

        harness_with_container.set_can_connect(self.container_name, True)
        sa_token_component = SATokenComponent(
            charm=harness_with_container.charm,
            name=self.token_k8s_name,
            audiences=self.audiences,
            sa_name=self.service_account_name,
            sa_namespace=self.namespace,
            filename=self.token_filename,
            path=sa_token_dir,
            expiration=self.expiration,
        )

        with (
            patch(K8S_CLIENT_LOAD_CONFIG_PATH),
            patch.object(CoreV1Api, K8S_CLIENT_CREATE_TOKEN_API) as mocked_k8s_client_create_token,
        ):
            # executing the charm logic:

            with pytest_raises(GenericCharmRuntimeError) as error:
                sa_token_component.configure_charm("mocked event")

            # asserting expectations meet reality:

            # charm status:
            assert error.value.msg == (
                f"Token for {self.service_account_name} ServiceAccount could not be created or "
                "persisted."
            )
            with pytest_raises(GenericCharmRuntimeError) as error:
                sa_token_component.status
            assert error.value.msg == (
                f"Token file for {self.service_account_name} ServiceAccount not present in charm."
            )

            # ServiceAccount token file:
            expected_sa_token_file_path = Path(sa_token_dir, self.token_filename)
            assert not expected_sa_token_file_path.exists()

            # K8s API calls:
            mocked_k8s_client_create_token.assert_not_called()
