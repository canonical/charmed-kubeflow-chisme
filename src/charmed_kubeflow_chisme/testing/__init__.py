# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Utilities for testing charms."""

from .serialized_data_interface import (
    RelationMetadata,
    add_data_to_sdi_relation,
    add_sdi_relation_to_harness,
)

__all__ = [
    RelationMetadata,
    add_data_to_sdi_relation,
    add_sdi_relation_to_harness,
]
