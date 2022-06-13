# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for working on batches of resources using the Lightkube library."""

from ._many import apply_many, delete_many

__all__ = [apply_many, delete_many]
