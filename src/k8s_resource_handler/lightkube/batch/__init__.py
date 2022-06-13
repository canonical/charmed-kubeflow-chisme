# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for working on batches of resources using the Lightkube library"""

from _sort_objects import _sort_objects
from _many import apply_many, delete_many
