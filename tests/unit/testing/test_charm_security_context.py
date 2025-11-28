# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest

from charmed_kubeflow_chisme.testing.charm_security_context import (
    generate_container_securitycontext_map,
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
                    "workload": {
                        "uid": 1000,
                        "gid": 1000,
                    },
                    "nginx": {
                        "uid": 101,
                        "gid": 101,
                    },
                }
            },
            170,
            {
                "workload": {"runAsUser": 1000, "runAsGroup": 1000},
                "nginx": {"runAsUser": 101, "runAsGroup": 101},
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
