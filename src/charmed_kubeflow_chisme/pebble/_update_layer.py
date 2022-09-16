# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import traceback
from logging import Logger

from ops.model import BlockedStatus, Container, MaintenanceStatus
from ops.pebble import ChangeError, Layer

from ..exceptions import ErrorWithStatus


def update_layer(container_name: str, container: Container, new_layer: Layer, logger: Logger):
    """Updates the Pebble configuration layer if changed.

    Args:
        container_name (str): The name of the container to update layer.
        container (ops.model.Container): The container object to update layer.
        new_layer (ops.pebble.Layer): The layer object to be updated to the container.
        logger (logging.Logger): A logger to use for logging.
    """
    if not container.can_connect():
        raise ErrorWithStatus("Waiting for pod startup to complete", MaintenanceStatus)

    current_layer = container.get_plan()

    if current_layer.services != new_layer.services:
        container.add_layer(container_name, new_layer, combine=True)
        try:
            logger.info("Pebble plan updated with new configuration, replanning")
            container.replan()
        except ChangeError:
            logger.error(traceback.format_exc())
            raise ErrorWithStatus("Failed to replan", BlockedStatus)
