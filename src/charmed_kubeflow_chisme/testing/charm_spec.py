# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""CharmSpec used for defining charms-dependencies during tests."""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class CharmSpec:
    """Dataclass used for defining charms that need to be deployed during tests."""

    charm: str
    channel: str
    trust: bool
    config: Optional[Dict]


def generate_context_from_charm_spec_dict(charms_dict: dict) -> dict:
    """Generate context for rendering a yaml template from dict with CharmSpec objects.

    Args:
        charms_dict: The dictionary containing CharmSpec objects

    Returns:
        Dictionary with keys like {charm_key}_charm, {charm_key}_channel, etc,
        ready for template rendering.
    """
    context = {}

    for charm_key, spec in charms_dict.items():
        # Handle charm names with hyphens convert to underscore for context keys)
        context_key = charm_key.replace("-", "_")

        # Add basic fields
        context[f"{context_key}_charm"] = spec.charm
        context[f"{context_key}_channel"] = spec.channel
        context[f"{context_key}_trust"] = spec.trust

        if spec.config:
            context[f"{context_key}_config"] = spec.config

    return context
