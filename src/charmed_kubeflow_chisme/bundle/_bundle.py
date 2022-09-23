# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Helper to work with Juju bundles, preserving comments in the YAML."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

from deepdiff import DeepDiff
from ruamel.yaml import YAML

from ..juju import Juju


class Bundle:
    """Juju bundle loader/dumper.

    This class uses ruamel.yaml instead of the typical pyyaml in order to preserve all comments,
    the order of the yaml, etc.  This way we can load/dump a yaml with comments without losing them
    or reordering the items.
    """

    def __init__(self, filename: Optional[str] = None):
        self._filename = filename
        self._data = None

        # Auto-load the bundle if a filename is provided
        if self._filename:
            self._load_bundle()

    def deepcopy(self) -> Bundle:
        """Returns a new deep copy of this Bundle."""
        newbundle = copy.deepcopy(self)
        return newbundle

    def diff(self, other: Bundle) -> DeepDiff:
        """Returns a diff between this and another object, in DeepDiff format."""
        return DeepDiff(self._data, other._data, ignore_order=True)

    def dump(self, filename: str):
        """Dumps as yaml to a file."""
        with open(filename, "w") as fout:
            yaml = YAML(typ="rt")
            yaml.dump(self.to_dict(), fout)

    def get_latest_revisions(self) -> Bundle:
        """Return a new Bundle that has the latest revisions of all charms in this bundle."""
        newbundle = self.deepcopy()

        applications = newbundle.applications

        for name, application in applications.items():
            # Skip charms we're not "tracking" a channel for
            if "_tracked_channel" not in application:
                continue

            charm_name = application["charm"]
            channel = application["_tracked_channel"]
            revision = application.get("revision", None)

            newest_revision = get_newest_charm_revision(charm_name, channel)

            if revision != newest_revision:
                # If revision is not up to date - update in situ from tracked channel
                application["revision"] = newest_revision

        return newbundle

    def _load_bundle(self):
        """Loads a YAML file as a bundle.

        This is triggered by default on __init__ if a filename is provided to the bundle, but can
        be used by a user to re-load the bundle from disk or to load a bundle if filename was not
        originally provided.

        This method will raise errors from pathlib.Path if the file does not exist.
        """
        yaml = YAML(typ="rt")
        self._data = yaml.load(Path(self._filename).read_text())

    def to_dict(self) -> dict:
        """Returns this bundle as a dict."""
        return self._data

    def __eq__(self, other) -> bool:
        """Returns True if this bundle is equal to another bundle."""
        return self._filename == other._filename and self.diff(other) == {}

    @property
    def applications(self) -> dict:
        """Returns the bundle's applications dict."""
        return self._data["applications"]


def get_newest_charm_revision(charm: str, channel: str) -> str:
    """Returns the newest revision of a charm in a channel."""
    charm_info = Juju.info(charm)
    channel_map = charm_info["channel-map"]
    try:
        tracked_channel_release = channel_map[channel]
    except KeyError:
        raise ValueError(f"No channel {channel} in `juju info {charm} --format yaml`")
    return tracked_channel_release["revision"]
