#!/usr/bin/python
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
from pathlib import Path

import yaml

def get_rock_image_name_from_rockcraft(self, file: str):
    """Reads a rockcraft.yaml file and returns the ROCK image name."""
    rockcraft = yaml.safe_load(Path(file).read_text())
    name = rockcraft["name"]
    version = rockcraft["version"]
    arch = list(rockcraft["platforms"].keys())[0]
    return f"{name}_{version}_{arch}:{version}"
