# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import yaml
from pathlib import Path

class TestRock:
    def __init__(self):
        """Initializes and return TestRock instance."""
        # no initialization is currently needed

    def get_rock_image_name_from_rockcraft(self, file):
        """Read ROCK information and return ROCK image name."""
        ROCKCRAFT = yaml.safe_load(Path(file).read_text())
        name = ROCKCRAFT["name"]
        version = ROCKCRAFT["version"]
        arch = list(ROCKCRAFT["platforms"].keys())[0]
        return f"{name}_{version}_{arch}:{version}"
