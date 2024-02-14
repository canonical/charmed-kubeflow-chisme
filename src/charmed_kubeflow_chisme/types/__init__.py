# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Reusable typing definitions, useful for adding type hints."""

from ._charm_status import CharmStatusType
from ._lightkube import LightkubeResourcesList, LightkubeResourceType, LightkubeResourceTypesSet

__all__ = [
    CharmStatusType,
    LightkubeResourcesList,
    LightkubeResourceType,
    LightkubeResourceTypesSet,
]
