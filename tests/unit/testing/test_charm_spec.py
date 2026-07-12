# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""Tests for CharmSpec."""

import pytest

from charmed_kubeflow_chisme.testing.charm_spec import (
    CharmSpec,
    generate_context_from_charm_spec_list,
)


class TestCharmSpec:
    def test_valid_with_channel(self):
        spec = CharmSpec(charm="my-charm", channel="latest/edge", trust=True)
        assert spec.charm == "my-charm"
        assert spec.channel == "latest/edge"
        assert spec.trust is True
        assert spec.revision is None

    def test_valid_with_revision(self):
        spec = CharmSpec(charm="my-charm", trust=True, revision=42)
        assert spec.charm == "my-charm"
        assert spec.channel is None
        assert spec.revision == 42

    def test_valid_with_channel_and_revision(self):
        spec = CharmSpec(charm="my-charm", channel="latest/edge", trust=True, revision=42)
        assert spec.channel == "latest/edge"
        assert spec.revision == 42

    def test_valid_with_config(self):
        spec = CharmSpec(
            charm="my-charm", channel="latest/edge", trust=True, config={"key": "value"}
        )
        assert spec.config == {"key": "value"}

    def test_invalid_charm_empty(self):
        with pytest.raises(ValueError, match="Charm name must be a non-empty string"):
            CharmSpec(charm="", channel="latest/edge", trust=True)

    def test_invalid_charm_not_string(self):
        with pytest.raises(ValueError, match="Charm name must be a non-empty string"):
            CharmSpec(charm=123, channel="latest/edge", trust=True)

    def test_invalid_no_channel_or_revision(self):
        with pytest.raises(ValueError, match="Either 'channel' or 'revision' must be provided"):
            CharmSpec(charm="my-charm", trust=True)

    def test_invalid_channel_format_no_slash(self):
        with pytest.raises(ValueError, match="Channel must be in format 'track/risk'"):
            CharmSpec(charm="my-charm", channel="edge", trust=True)

    def test_invalid_channel_not_string(self):
        with pytest.raises(ValueError, match="Channel must be in format 'track/risk'"):
            CharmSpec(charm="my-charm", channel=123, trust=True)

    def test_invalid_revision_not_int(self):
        with pytest.raises(ValueError, match="Revision must be a positive integer"):
            CharmSpec(charm="my-charm", trust=True, revision="42")

    def test_invalid_revision_zero(self):
        with pytest.raises(ValueError, match="Revision must be a positive integer"):
            CharmSpec(charm="my-charm", trust=True, revision=0)

    def test_invalid_revision_negative(self):
        with pytest.raises(ValueError, match="Revision must be a positive integer"):
            CharmSpec(charm="my-charm", trust=True, revision=-1)

    def test_invalid_trust_not_bool(self):
        with pytest.raises(ValueError, match="Trust must be a boolean value"):
            CharmSpec(charm="my-charm", channel="latest/edge", trust="yes")

    def test_invalid_config_not_dict(self):
        with pytest.raises(ValueError, match="Config must be a dictionary"):
            CharmSpec(charm="my-charm", channel="latest/edge", trust=True, config=["a", "b"])


class TestGenerateContextFromCharmSpecList:
    def test_generates_context(self):
        charms = [
            CharmSpec(charm="my-charm", channel="latest/edge", trust=True),
        ]
        context = generate_context_from_charm_spec_list(charms)
        assert context["my_charm_charm"] == "my-charm"
        assert context["my_charm_channel"] == "latest/edge"
        assert context["my_charm_trust"] is True

    def test_generates_context_with_config(self):
        charms = [
            CharmSpec(
                charm="my-charm", channel="latest/edge", trust=True, config={"key": "value"}
            ),
        ]
        context = generate_context_from_charm_spec_list(charms)
        assert context["my_charm_config"] == {"key": "value"}

    def test_generates_context_revision_only(self):
        charms = [
            CharmSpec(charm="my-charm", trust=True, revision=42),
        ]
        context = generate_context_from_charm_spec_list(charms)
        assert context["my_charm_channel"] is None
        assert context["my_charm_trust"] is True
