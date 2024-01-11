# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
from logging import Logger

from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    StatusBase,
    Unit,
    WaitingStatus,
)


def set_and_log_status(unit: Unit, logger: Logger, status: StatusBase):
    """Sets the status of the charm and logs the status message.

    Args:
        unit: The unit of which the status will be set
        logger: The logger used for logging status' message
        status: The status to set
    """
    unit.status = status

    log_destination_map = {
        ActiveStatus: logger.info,
        BlockedStatus: logger.warning,
        MaintenanceStatus: logger.info,
        WaitingStatus: logger.info,
    }

    log_destination_map[type(status)](status.message)
