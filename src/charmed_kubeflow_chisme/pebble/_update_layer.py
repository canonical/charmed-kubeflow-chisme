# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import traceback
from logging import Logger

from ops.model import BlockedStatus, Container
from ops.pebble import ChangeError, Layer

from ..exceptions import ErrorWithStatus


def update_layer(container_name: str, container: Container, new_layer: Layer, logger: Logger):
    """Updates the Pebble configuration layer if changed."""
    current_layer = container.get_plan()

    if current_layer.services != new_layer.services:
        container.add_layer(container_name, new_layer, combine=True)
        try:
            logger.info("Pebble plan updated with new configuration, replanning")
            container.replan()
        except ChangeError:
            logger.error(traceback.format_exc())
            raise ErrorWithStatus("Failed to replan", BlockedStatus)
