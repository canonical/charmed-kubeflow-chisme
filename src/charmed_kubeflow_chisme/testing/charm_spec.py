# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""CharmSpec used for defining charms-dependencies during tests."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CharmSpec:
    """Dataclass used for defining charms that need to be deployed during tests."""

    charm: str
    channel: str
    trust: bool
    config: Optional[Dict] = None

    def __post_init__(self):
        """Simple type validation for class attributes."""
        if not isinstance(self.charm, str) or not self.charm:
            raise ValueError("Charm name must be a non-empty string")

        if not isinstance(self.channel, str) or "/" not in self.channel:
            raise ValueError("Channel must be in format 'track/risk'")

        if not isinstance(self.trust, bool):
            raise ValueError("Trust must be a boolean value")

        if self.config is not None:
            if not isinstance(self.config, dict):
                raise ValueError("Config must be a dictionary")


def generate_context_from_charm_spec_list(charms: List[CharmSpec]) -> dict:
    """Generate context for rendering a yaml template from a list of CharmSpec objects.

    Args:
        charms: The list containing CharmSpec objects

    Returns:
        Dictionary with keys like {charm_name}_charm, {charm_key}_channel, etc,
        ready for template rendering.
    """
    context = {}
    for charm in charms:
        # Handle charm names with hyphens convert to underscore for context keys
        context_key = charm.charm.replace("-", "_")

        # Add basic fields
        context[f"{context_key}_charm"] = charm.charm
        context[f"{context_key}_channel"] = charm.channel
        context[f"{context_key}_trust"] = charm.trust

        if charm.config:
            context[f"{context_key}_config"] = charm.config

    return context
