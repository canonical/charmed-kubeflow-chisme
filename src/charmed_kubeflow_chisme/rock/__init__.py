# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for Handling Rocks in Charms and Tests."""

from ._test_rock import get_rock_image_name_from_rockcraft
from ._test_rock import get_rock_image_version_from_rockcraft

__all__ = [get_rock_image_name_from_rockcraft, get_rock_image_version_from_rockcraft]
