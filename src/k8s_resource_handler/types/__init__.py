# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Reusable typing definitions, useful for adding type hints."""

from ._charm_status import CharmStatusType
from ._lightkube import LightkubeResourcesList, LightkubeResourceType

__all__ = [
    CharmStatusType,
    LightkubeResourcesList,
    LightkubeResourceType,
]
