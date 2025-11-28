# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for testing security context and user privileges in charms."""
import subprocess
from typing import Dict, TypedDict

import lightkube
from lightkube.resources.core_v1 import Pod


class ContainerSecurityContext(TypedDict):
    """TypedDict representing Kubernetes container security context settings.

    This TypedDict defines the structure for container security context configurations,
    specifically focusing on user/group IDs and non-root execution requirements. It's
    used to type-hint dictionaries containing security context information for
    Kubernetes containers.

    Attributes:
        runAsUser (int | None): The UID to run the container's entry point as.
            Corresponds to the Kubernetes securityContext.runAsUser field.
        runAsGroup (int | None): The GID to run the container's entry point as.
            Corresponds to the Kubernetes securityContext.runAsGroup field.
        runAsNonRoot (bool | None): Indicates that the container must run as a non-root
            user. If true, the kubelet will validate the image at runtime to ensure it
            does not run as UID 0 (root). Corresponds to the Kubernetes
            securityContext.runAsNonRoot field.

    Note:
        All fields can be None to indicate they are not set or not applicable.
        The field names follow Kubernetes naming conventions (camelCase) rather than
        Python conventions (snake_case), hence the noqa N815 annotations.

    Example:
        >>> context: ContainerSecurityContext = {
        ...     "runAsUser": 1000,
        ...     "runAsGroup": 1000,
        ...     "runAsNonRoot": True,
        ... }
        >>> print(context["runAsUser"])
        1000
    """

    runAsUser: int | None  # noqa N815
    runAsGroup: int | None  # noqa N815
    runAsNonRoot: bool | None  # noqa N815


def generate_container_securitycontext_map(
    metadata_yaml: dict, juju_user_id: int = 170
) -> dict[str, ContainerSecurityContext]:
    """Generate a mapping of container names to their security context UID/GID settings.

    This function extracts container security context information from a charm's metadata
    and creates a mapping that includes both application containers and the charm container.

    Args:
        metadata_yaml (dict): The charm's metadata dictionary, expected to contain a
            "containers" key with container definitions including "uid" and "gid" fields.
        juju_user_id (int): The user ID and group ID to use for the charm container.
            Defaults to 170, which is the standard Juju user ID.

    Returns:
        dict: A mapping of container names to security context dictionaries. Each
            security context contains "runAsUser" and "runAsGroup" keys. Includes
            entries for all containers defined in metadata plus a "charm" entry.

    Example:
        >>> metadata = {
        ...     "containers": {
        ...         "app": {"uid": 1000, "gid": 1000},
        ...         "nginx": {"uid": 101, "gid": 101}
        ...     }
        ... }
        >>> generate_container_securitycontext_map(metadata)
        {
            "app": {"runAsUser": 1000, "runAsGroup": 1000},
            "nginx": {"runAsUser": 101, "runAsGroup": 101},
            "charm": {"runAsUser": 170, "runAsGroup": 170}
        }
    """
    c_uid_map = {}
    for k, v in metadata_yaml.get("containers", {}).items():
        c_uid_map[k] = ContainerSecurityContext(
            runAsUser=v["uid"],
            runAsGroup=v["gid"],
        )
    c_uid_map["charm"] = {"runAsUser": juju_user_id, "runAsGroup": juju_user_id}
    return c_uid_map


def get_pod_names(model: str, application_name: str) -> list[str]:
    """Retrieve names of all pods belonging to a specific Juju application.

    This function uses kubectl to query the Kubernetes cluster for pods that match
    the given application name within the specified Juju model namespace. It filters
    pods by the standard Juju label "app.kubernetes.io/name".

    Args:
        model (str): The name of the Juju model, which corresponds to the Kubernetes
            namespace where the pods are deployed.
        application_name (str): The name of the Juju application whose pods should
            be retrieved. This matches the "app.kubernetes.io/name" label.

    Returns:
        list[str]: A list of pod names matching the application. Returns an empty
            list if no pods are found or if the kubectl command fails.
    """
    cmd = [
        "kubectl",
        "get",
        "pods",
        f"-n{model}",
        f"-lapp.kubernetes.io/name={application_name}",
        "--no-headers",
        "-o=custom-columns=NAME:.metadata.name",
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
    )
    stdout = proc.stdout.decode("utf8")
    return stdout.split()


def assert_security_context(
    lightkube_client: lightkube.Client,
    pod_name: str,
    container_name: str,
    container_securitycontext_map: Dict[str, ContainerSecurityContext],
    model_name: str,
) -> None:
    """Assert that a container's security context matches expected UID/GID settings.

    This function retrieves the actual security context from a running container in a
    Kubernetes pod and compares it against the expected values provided in the
    container_securitycontext_map. It raises an AssertionError if any security context attribute
    (runAsUser or runAsGroup) doesn't match the expected value.

    Args:
        lightkube_client (lightkube.Client): A configured lightkube client instance
            for making HTTP requests to the Kubernetes cluster.
        pod_name (str): The name of the pod containing the container to check.
        container_name (str): The name of the specific container within the pod
            whose security context should be verified.
        container_securitycontext_map (dict): A mapping of container names to their expected
            security context settings. Each entry should contain a dictionary with
            "runAsUser" and "runAsGroup" keys. Typically generated by
            generate_container_uid_map().
        model_name (str): The name of the Juju model, which corresponds to the
            Kubernetes namespace where the pod is running.

    Raises:
        AssertionError: If any security context attribute doesn't match the expected
            value from container_securitycontext_map.
        StopIteration: If no container with the specified name is found in the pod.
    """
    containers: list = lightkube_client.get(Pod, pod_name, namespace=model_name).spec.containers
    container = next((c for c in containers if c.name == container_name), None)
    security_context = container.securityContext
    # assert user ID is the one defined in metadata.yaml
    for key, value in container_securitycontext_map.get(container_name).items():
        assert getattr(security_context, key) == value
