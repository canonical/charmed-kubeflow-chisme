# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
from pathlib import Path

import yaml


class TestRock:
    """Test class for ROCKs."""

    def __init__(self):
        """Initializes and return TestRock instance."""
        # no initialization is currently needed

    def get_rock_image_name_from_rockcraft(self, file):
        """Read ROCK information and return ROCK image name."""
        rockcraft = yaml.safe_load(Path(file).read_text())
        name = rockcraft["name"]
        version = rockcraft["version"]
        arch = list(rockcraft["platforms"].keys())[0]
        return f"{name}_{version}_{arch}:{version}"
