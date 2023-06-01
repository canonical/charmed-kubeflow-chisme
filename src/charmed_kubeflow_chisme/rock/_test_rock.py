#!/usr/bin/python
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
from pathlib import Path

import yaml


class TestRock(rockcraft_file: str):
    """Class for testing ROCKs."""
    self._rockcraft = yaml.safe_load(Path(rockcraft_file).read_text())


def get_rock_image_version_from_rockcraft(self):
    """Returns the ROCK image version."""
    version = self._rockcraft["version"]
    return version


def get_rock_image_name_from_rockcraft(self):
    """Returns the ROCK image name."""
    name = self._rockcraft["name"]
    version = self.get_rock_image_version_from_rockcraft(file)
    arch = list(self._rockcraft["platforms"].keys())[0]
    return f"{name}_{version}_{arch}"
