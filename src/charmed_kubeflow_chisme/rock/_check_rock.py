#!/usr/bin/python
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
from pathlib import Path

import yaml


class CheckRock:
    """Class for testing ROCKs."""

    def __init__(self, rockcraft_file: str):
        """Initialize class with information from given rockcraft file."""
        self._rockcraft = yaml.safe_load(Path(rockcraft_file).read_text())

    def get_name(self):
        """Returns the name of the ROCK."""
        return self._rockcraft["name"]

    def get_version(self):
        """Returns the ROCK image version."""
        version = self._rockcraft["version"]
        return version

    def get_rock_filename(self):
        """Returns the ROCK filename."""
        name = self._rockcraft["name"]
        version = self.get_version()
        arch = list(self._rockcraft["platforms"].keys())[0]
        return f"{name}_{version}_{arch}.rock"

    def get_services(self):
        """Returns dictionary of services defined in ROCK."""
        return self._rockcraft["services"]
