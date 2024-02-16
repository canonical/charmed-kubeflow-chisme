# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from logging import Logger

from ops import Container
from ops.model import ErrorStatus, MaintenanceStatus, ModelError
from ops.pebble import CheckStatus

from ..exceptions import ErrorWithStatus


def check_workload_health(
    container: Container, container_name: str, health_check: str, logger: Logger
):
    """Check the workload container's health by checking the passed health check's status.

    Raises if health check's status is not up.

    Args:
        container: The container object of which the health will be checked.
        container_name: The name of the container object passed for logging purposes.
        health_check: The name of the health check used.
        logger: The logger used for logging status' message.
    """
    try:
        check_status = container.get_check(health_check).status
    except ModelError:
        raise ErrorWithStatus(f"Failed to run health check on {container} container", ErrorStatus)
    if check_status != CheckStatus.UP:
        logger.error(f"Container {container_name} failed health check.")
        raise ErrorWithStatus("Workload failed health check", MaintenanceStatus)
