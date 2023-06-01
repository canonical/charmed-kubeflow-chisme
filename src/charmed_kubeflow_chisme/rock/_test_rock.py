#!/usr/bin/python
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
from pathlib import Path

import yaml


class TestRock():
    """Class for testing ROCKs."""
    def __init__(self, rockcraft_file: str):
        """Initialize class with information from given rockcraft file."""
        self._rockcraft = yaml.safe_load(Path(rockcraft_file).read_text())


    def get_version(self):
        """Returns the ROCK image version."""
        version = self._rockcraft["version"]
        return version


    def get_image_name(self):
        """Returns the ROCK image name."""
        name = self._rockcraft["name"]
        version = self.get_version()
        arch = list(self._rockcraft["platforms"].keys())[0]
        return f"{name}_{version}_{arch}"
