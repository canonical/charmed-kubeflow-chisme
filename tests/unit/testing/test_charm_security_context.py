# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from charmed_kubeflow_chisme.testing.charm_security_context import (
    assert_security_context,
    generate_container_securitycontext_map,
    get_pod_names,
)


@pytest.mark.parametrize(
    "metadata_yaml,juju_user_id,expected",
    [
        # Test case: Single container with default juju_user_id
        (
            {
                "containers": {
                    "workload": {
                        "uid": 1000,
                        "gid": 1000,
                    }
                }
            },
            170,
            {
                "workload": {"runAsUser": 1000, "runAsGroup": 1000},
                "charm": {"runAsUser": 170, "runAsGroup": 170},
            },
        ),
        # Test case: Multiple containers with default juju_user_id
        (
            {
                "containers": {
                    "workload1": {
                        "uid": 1000,
                        "gid": 1000,
                    },
                    "workload2": {
                        "uid": 101,
                        "gid": 101,
                    },
                }
            },
            170,
            {
                "workload1": {"runAsUser": 1000, "runAsGroup": 1000},
                "workload2": {"runAsUser": 101, "runAsGroup": 101},
                "charm": {"runAsUser": 170, "runAsGroup": 170},
            },
        ),
        # Test case: Single container with custom juju_user_id
        (
            {
                "containers": {
                    "workload": {
                        "uid": 1000,
                        "gid": 1000,
                    }
                }
            },
            500,
            {
                "workload": {"runAsUser": 1000, "runAsGroup": 1000},
                "charm": {"runAsUser": 500, "runAsGroup": 500},
            },
        ),
        # Test case: Empty containers dict
        (
            {"containers": {}},
            170,
            {
                "charm": {"runAsUser": 170, "runAsGroup": 170},
            },
        ),
        # Test case: No containers key in metadata
        (
            {},
            170,
            {
                "charm": {"runAsUser": 170, "runAsGroup": 170},
            },
        ),
        # Test case: Container with different uid and gid
        (
            {
                "containers": {
                    "workload": {
                        "uid": 999,
                        "gid": 888,
                    }
                }
            },
            170,
            {
                "workload": {"runAsUser": 999, "runAsGroup": 888},
                "charm": {"runAsUser": 170, "runAsGroup": 170},
            },
        ),
        # Test case: Multiple containers with varied UIDs/GIDs
        (
            {
                "containers": {
                    "workload1": {
                        "uid": 1000,
                        "gid": 1000,
                    },
                    "workload2": {
                        "uid": 101,
                        "gid": 101,
                    },
                    "workload3": {
                        "uid": 70,
                        "gid": 70,
                    },
                }
            },
            170,
            {
                "workload1": {"runAsUser": 1000, "runAsGroup": 1000},
                "workload2": {"runAsUser": 101, "runAsGroup": 101},
                "workload3": {"runAsUser": 70, "runAsGroup": 70},
                "charm": {"runAsUser": 170, "runAsGroup": 170},
            },
        ),
    ],
    ids=[
        "single_container_default_juju_id",
        "multiple_containers_default_juju_id",
        "single_container_custom_juju_id",
        "empty_containers",
        "no_containers_key",
        "different_uid_gid",
        "multiple_varied_containers",
    ],
)
def test_generate_container_securitycontext_map(metadata_yaml, juju_user_id, expected):
    """Test generate_container_securitycontext_map with various metadata configurations."""
    result = generate_container_securitycontext_map(metadata_yaml, juju_user_id)
    assert result == expected


@pytest.mark.parametrize(
    "metadata_yaml",
    [
        # Test with single container
        {
            "containers": {
                "workload": {
                    "uid": 1000,
                    "gid": 1000,
                }
            }
        },
        # Test with multiple containers
        {
            "containers": {
                "workload1": {
                    "uid": 1000,
                    "gid": 1000,
                },
                "workload2": {
                    "uid": 101,
                    "gid": 101,
                },
            }
        },
    ],
    ids=["single_container", "multiple_containers"],
)
def test_generate_container_securitycontext_map_always_includes_charm(metadata_yaml):
    """Test that charm container is always included in the result."""
    result = generate_container_securitycontext_map(metadata_yaml)
    assert "charm" in result
    assert result["charm"]["runAsUser"] == 170
    assert result["charm"]["runAsGroup"] == 170


@pytest.mark.parametrize(
    "metadata_yaml,expected_keys",
    [
        (
            {
                "containers": {
                    "workload": {"uid": 1000, "gid": 1000},
                }
            },
            {"workload", "charm"},
        ),
        (
            {
                "containers": {
                    "workload1": {"uid": 1000, "gid": 1000},
                    "workload2": {"uid": 101, "gid": 101},
                }
            },
            {"workload1", "workload2", "charm"},
        ),
        (
            {
                "containers": {
                    "workload1": {"uid": 1000, "gid": 1000},
                    "workload2": {"uid": 101, "gid": 101},
                    "workload3": {"uid": 70, "gid": 70},
                }
            },
            {"workload1", "workload2", "workload3", "charm"},
        ),
    ],
    ids=["one_container", "two_containers", "three_containers"],
)
def test_generate_container_securitycontext_map_correct_keys(metadata_yaml, expected_keys):
    """Test that all expected container names are present as keys."""
    result = generate_container_securitycontext_map(metadata_yaml)
    assert set(result.keys()) == expected_keys


@pytest.mark.parametrize(
    "metadata_yaml,container_name",
    [
        (
            {
                "containers": {
                    "workload1": {"uid": 1000, "gid": 1000},
                }
            },
            "workload1",
        ),
        (
            {
                "containers": {
                    "workload2": {"uid": 101, "gid": 101},
                }
            },
            "workload2",
        ),
    ],
    ids=["workload1_container", "workload2_container"],
)
def test_generate_container_securitycontext_map_security_context_structure(
    metadata_yaml, container_name
):
    """Test that each container has the correct security context structure."""
    result = generate_container_securitycontext_map(metadata_yaml)
    assert "runAsUser" in result[container_name]
    assert "runAsGroup" in result[container_name]
    assert (
        result[container_name]["runAsUser"] == metadata_yaml["containers"][container_name]["uid"]
    )
    assert (
        result[container_name]["runAsGroup"] == metadata_yaml["containers"][container_name]["gid"]
    )


@pytest.mark.parametrize(
    "juju_user_id",
    [0, 100, 170, 999, 1000, 65534],
    ids=["root", "100", "default_170", "999", "1000", "nobody"],
)
def test_generate_container_securitycontext_map_custom_juju_user_ids(juju_user_id):
    """Test that custom juju_user_id values are correctly applied to charm container."""
    metadata_yaml = {
        "containers": {
            "workload": {"uid": 1000, "gid": 1000},
        }
    }
    result = generate_container_securitycontext_map(metadata_yaml, juju_user_id)
    assert result["charm"]["runAsUser"] == juju_user_id
    assert result["charm"]["runAsGroup"] == juju_user_id


def test_generate_container_securitycontext_map_default_juju_user_id():
    """Test that the default juju_user_id is 170."""
    metadata_yaml = {
        "containers": {
            "workload": {"uid": 1000, "gid": 1000},
        }
    }
    # Call without specifying juju_user_id to use default
    result = generate_container_securitycontext_map(metadata_yaml)
    assert result["charm"]["runAsUser"] == 170
    assert result["charm"]["runAsGroup"] == 170


@pytest.mark.parametrize(
    "uid,gid",
    [
        (0, 0),
        (1000, 2000),
        (65534, 65534),
    ],
    ids=["root", "different_uid_gid", "max_uid"],
)
def test_generate_container_securitycontext_map_various_uid_gid_combinations(uid, gid):
    """Test various UID/GID combinations are correctly mapped."""
    metadata_yaml = {
        "containers": {
            "test": {"uid": uid, "gid": gid},
        }
    }
    result = generate_container_securitycontext_map(metadata_yaml)
    assert result["test"]["runAsUser"] == uid
    assert result["test"]["runAsGroup"] == gid


@pytest.mark.parametrize(
    "stdout,expected_pod_names",
    [
        # Single pod
        ("charm-app-0\n", ["charm-app-0"]),
        # Multiple pods
        ("charm-app-0\ncharm-app-1\ncharm-app-2\n", ["charm-app-0", "charm-app-1", "charm-app-2"]),
        # Empty output (no pods found)
        ("", []),
        # Single pod without trailing newline
        ("charm-app-0", ["charm-app-0"]),
        # Pods with longer names
        (
            "kubeflow-pod-0\nkubeflow-pod-1\n",
            ["kubeflow-pod-0", "kubeflow-pod-1"],
        ),
    ],
    ids=[
        "single_pod",
        "multiple_pods",
        "no_pods",
        "single_pod_no_newline",
        "longer_names",
    ],
)
@patch("subprocess.run")
def test_get_pod_names_various_outputs(mock_run, stdout, expected_pod_names):
    """Test get_pod_names with various kubectl output formats."""
    # Setup mock
    mock_process = MagicMock()
    mock_process.stdout.decode.return_value = stdout
    mock_run.return_value = mock_process

    # Call function
    result = get_pod_names("test-model", "charm-app")

    # Verify result
    assert result == expected_pod_names

    # Verify kubectl was called correctly
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "kubectl"
    assert call_args[1] == "get"
    assert call_args[2] == "pods"
    assert "-ntest-model" in call_args
    assert "-lapp.kubernetes.io/name=charm-app" in call_args


@pytest.mark.parametrize(
    "model_name,application_name,expected_namespace,expected_label",
    [
        ("dev", "charm-pod", "-ndev", "-lapp.kubernetes.io/name=charm-pod"),
        ("kubeflow", "kubeflow-pod", "-nkubeflow", "-lapp.kubernetes.io/name=kubeflow-pod"),
        ("test-123", "app-456", "-ntest-123", "-lapp.kubernetes.io/name=app-456"),
    ],
    ids=["dev_model", "kubeflow_model", "numeric_names"],
)
@patch("subprocess.run")
def test_get_pod_names_command_construction(
    mock_run, model_name, application_name, expected_namespace, expected_label
):
    """Test that kubectl command is constructed correctly with different inputs."""
    # Setup mock
    mock_process = MagicMock()
    mock_process.stdout.decode.return_value = "pod-0\n"
    mock_run.return_value = mock_process

    # Call function
    get_pod_names(model_name, application_name)

    # Verify kubectl command
    call_args = mock_run.call_args[0][0]
    assert expected_namespace in call_args
    assert expected_label in call_args
    assert "--no-headers" in call_args
    assert "-o=custom-columns=NAME:.metadata.name" in call_args


@patch("subprocess.run")
def test_get_pod_names_subprocess_called_with_correct_args(mock_run):
    """Test that subprocess.run is called with correct arguments."""
    # Setup mock
    mock_process = MagicMock()
    mock_process.stdout.decode.return_value = "pod-0\n"
    mock_run.return_value = mock_process

    # Call function
    get_pod_names("my-model", "charm-app")

    # Verify subprocess.run was called with stdout=PIPE
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["stdout"] == subprocess.PIPE


@patch("subprocess.run")
def test_get_pod_names_handles_whitespace(mock_run):
    """Test that get_pod_names handles various whitespace in output."""
    # Setup mock with extra whitespace
    mock_process = MagicMock()
    mock_process.stdout.decode.return_value = "pod-0\n\npod-1\n  \npod-2\n"
    mock_run.return_value = mock_process

    # Call function
    result = get_pod_names("my-model", "charm-app")

    # Result should include empty strings from extra newlines
    # This tests the actual behavior of str.split()
    assert "pod-0" in result
    assert "pod-1" in result
    assert "pod-2" in result


@patch("subprocess.run")
def test_get_pod_names_empty_string_results_in_empty_list(mock_run):
    """Test that empty string output results in appropriate list."""
    # Setup mock with empty string
    mock_process = MagicMock()
    mock_process.stdout.decode.return_value = ""
    mock_run.return_value = mock_process

    # Call function
    result = get_pod_names("my-model", "charm-app")

    # Empty string split should give []
    assert result == []


@patch("subprocess.run")
def test_get_pod_names_decodes_utf8(mock_run):
    """Test that stdout is decoded as UTF-8."""
    # Setup mock
    mock_process = MagicMock()
    mock_run.return_value = mock_process

    # Call function
    get_pod_names("my-model", "charm-app")

    # Verify decode was called with "utf8"
    mock_process.stdout.decode.assert_called_once_with("utf8")


@pytest.mark.parametrize(
    "pod_count,expected_count",
    [
        (1, 1),
        (3, 3),
        (5, 5),
        (10, 10),
    ],
    ids=["one_pod", "three_pods", "five_pods", "ten_pods"],
)
@patch("subprocess.run")
def test_get_pod_names_various_pod_counts(mock_run, pod_count, expected_count):
    """Test get_pod_names with different numbers of pods."""
    # Create stdout with specified number of pods
    pod_names = [f"pod-{i}" for i in range(pod_count)]
    stdout = "\n".join(pod_names) + "\n"

    # Setup mock
    mock_process = MagicMock()
    mock_process.stdout.decode.return_value = stdout
    mock_run.return_value = mock_process

    # Call function
    result = get_pod_names("my-model", "charm-app")

    # Verify result
    assert len(result) == expected_count
    assert result == pod_names


def create_mock_container(name, run_as_user, run_as_group, run_as_non_root=None):
    """Helper function to create a mock container with security context."""
    container = Mock()
    container.name = name
    container.securityContext = Mock()
    container.securityContext.runAsUser = run_as_user
    container.securityContext.runAsGroup = run_as_group
    if run_as_non_root is not None:
        container.securityContext.runAsNonRoot = run_as_non_root
    return container


@pytest.mark.parametrize(
    "container_name,run_as_user,run_as_group,expected_map",
    [
        # Test case: Matching UID/GID
        (
            "workload",
            1000,
            1000,
            {"workload": {"runAsUser": 1000, "runAsGroup": 1000}},
        ),
        # Test case: Different UID and GID
        (
            "workload",
            999,
            888,
            {"workload": {"runAsUser": 999, "runAsGroup": 888}},
        ),
        # Test case: Root user
        (
            "workload",
            0,
            0,
            {"workload": {"runAsUser": 0, "runAsGroup": 0}},
        ),
    ],
    ids=["matching_uid_gid", "different_uid_gid", "root_user"],
)
def test_assert_security_context_success(container_name, run_as_user, run_as_group, expected_map):
    """Test assert_security_context with matching security contexts."""
    # Setup mocks
    mock_client = Mock()
    mock_pod = Mock()
    mock_container = create_mock_container(container_name, run_as_user, run_as_group)
    mock_pod.spec.containers = [mock_container]
    mock_client.get.return_value = mock_pod

    # Call function - should not raise
    assert_security_context(
        mock_client,
        "test-pod-0",
        container_name,
        expected_map,
        "test-model",
    )

    # Verify client.get was called correctly
    mock_client.get.assert_called_once()


@pytest.mark.parametrize(
    "expected_user,actual_user,expected_group,actual_group",
    [
        (1000, 999, 1000, 1000),  # Wrong user
        (1000, 1000, 1000, 999),  # Wrong group
        (1000, 999, 1000, 888),  # Both wrong
        (1000, 0, 1000, 1000),  # User running as root unexpectedly
    ],
    ids=["wrong_user", "wrong_group", "both_wrong", "unexpected_root"],
)
def test_assert_security_context_mismatch_raises(
    expected_user, actual_user, expected_group, actual_group
):
    """Test assert_security_context raises AssertionError on mismatch."""
    # Setup mocks
    mock_client = Mock()
    mock_pod = Mock()
    mock_container = create_mock_container("workload", actual_user, actual_group)
    mock_pod.spec.containers = [mock_container]
    mock_client.get.return_value = mock_pod

    expected_map = {"workload": {"runAsUser": expected_user, "runAsGroup": expected_group}}

    # Call function - should raise AssertionError
    with pytest.raises(AssertionError):
        assert_security_context(
            mock_client,
            "test-pod-0",
            "workload",
            expected_map,
            "test-model",
        )


def test_assert_security_context_multiple_containers():
    """Test assert_security_context finds correct container in multi-container pod."""
    # Setup mocks with multiple containers
    mock_client = Mock()
    mock_pod = Mock()
    container1 = create_mock_container("workload1", 1000, 1000)
    container2 = create_mock_container("workload2", 2000, 2000)
    container3 = create_mock_container("workload3", 3000, 3000)
    mock_pod.spec.containers = [container1, container2, container3]
    mock_client.get.return_value = mock_pod

    expected_map = {"workload2": {"runAsUser": 2000, "runAsGroup": 2000}}

    # Call function - should check workload2
    assert_security_context(
        mock_client,
        "test-pod-0",
        "workload2",
        expected_map,
        "test-model",
    )


def test_assert_security_context_container_not_found():
    """Test assert_security_context when container name doesn't exist."""
    # Setup mocks
    mock_client = Mock()
    mock_pod = Mock()
    mock_container = create_mock_container("workload1", 1000, 1000)
    mock_pod.spec.containers = [mock_container]
    mock_client.get.return_value = mock_pod

    expected_map = {"nonexistent": {"runAsUser": 1000, "runAsGroup": 1000}}

    # Call function - should raise AttributeError when accessing None.securityContext
    with pytest.raises(AttributeError):
        assert_security_context(
            mock_client,
            "test-pod-0",
            "nonexistent",
            expected_map,
            "test-model",
        )


@pytest.mark.parametrize(
    "pod_name,model_name",
    [
        ("test-pod-0", "test-model"),
        ("charm-operator-0", "kubeflow"),
    ],
    ids=["test_environment", "kubeflow_environment"],
)
def test_assert_security_context_pod_retrieval(pod_name, model_name):
    """Test that assert_security_context retrieves the correct pod."""
    # Setup mocks
    mock_client = Mock()
    mock_pod = Mock()
    mock_container = create_mock_container("workload", 1000, 1000)
    mock_pod.spec.containers = [mock_container]
    mock_client.get.return_value = mock_pod

    expected_map = {"workload": {"runAsUser": 1000, "runAsGroup": 1000}}

    # Call function
    assert_security_context(
        mock_client,
        pod_name,
        "workload",
        expected_map,
        model_name,
    )

    # Verify correct pod was retrieved
    call_args = mock_client.get.call_args
    # First positional arg should be Pod class, second is pod_name
    assert call_args[0][1] == pod_name
    # Namespace should be model_name
    assert call_args[1]["namespace"] == model_name


def test_assert_security_context_charm_container():
    """Test assert_security_context with charm container (default Juju user)."""
    # Setup mocks
    mock_client = Mock()
    mock_pod = Mock()
    charm_container = create_mock_container("charm", 170, 170)
    mock_pod.spec.containers = [charm_container]
    mock_client.get.return_value = mock_pod

    expected_map = {"charm": {"runAsUser": 170, "runAsGroup": 170}}

    # Call function - should not raise
    assert_security_context(
        mock_client,
        "test-pod-0",
        "charm",
        expected_map,
        "test-model",
    )


def test_assert_security_context_only_checks_specified_keys():
    """Test that assert_security_context only checks keys present in expected map."""
    # Setup mocks - container has runAsNonRoot but map doesn't include it
    mock_client = Mock()
    mock_pod = Mock()
    mock_container = create_mock_container("workload", 1000, 1000, run_as_non_root=True)
    mock_pod.spec.containers = [mock_container]
    mock_client.get.return_value = mock_pod

    # Map only includes runAsUser and runAsGroup
    expected_map = {"workload": {"runAsUser": 1000, "runAsGroup": 1000}}

    # Call function - should not raise even though runAsNonRoot is not checked
    assert_security_context(
        mock_client,
        "test-pod-0",
        "workload",
        expected_map,
        "test-model",
    )


@pytest.mark.parametrize(
    "container_count",
    [1, 2, 5, 10],
    ids=["one_container", "two_containers", "five_containers", "ten_containers"],
)
def test_assert_security_context_finds_target_in_varying_pod_sizes(container_count):
    """Test assert_security_context can find target container in pods with varying container counts."""
    # Setup mocks with multiple containers
    mock_client = Mock()
    mock_pod = Mock()

    # Create multiple containers, target is in the middle
    containers = []
    for i in range(container_count):
        containers.append(create_mock_container(f"workload{i}", 1000 + i, 1000 + i))

    mock_pod.spec.containers = containers
    mock_client.get.return_value = mock_pod

    # Check the middle container
    target_index = container_count // 2
    target_name = f"workload{target_index}"
    expected_map = {
        target_name: {"runAsUser": 1000 + target_index, "runAsGroup": 1000 + target_index}
    }

    # Call function - should find and verify the target container
    assert_security_context(
        mock_client,
        "test-pod-0",
        target_name,
        expected_map,
        "test-model",
    )


def test_assert_security_context_empty_expected_map():
    """Test assert_security_context with empty security context map for a container."""
    # Setup mocks
    mock_client = Mock()
    mock_pod = Mock()
    mock_container = create_mock_container("workload", 1000, 1000)
    mock_pod.spec.containers = [mock_container]
    mock_client.get.return_value = mock_pod

    # Empty map for the container - no assertions should be made
    expected_map = {"workload": {}}

    # Call function - should not raise as there are no keys to check
    assert_security_context(
        mock_client,
        "test-pod-0",
        "workload",
        expected_map,
        "test-model",
    )
