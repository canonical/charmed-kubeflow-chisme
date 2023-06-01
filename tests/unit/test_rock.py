# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
import subprocess

from charmed_kubeflow_chisme.rock import TestRock
from pathlib import Path


data_dir = Path(__file__).parent.joinpath("data")

def test_cli_usage():
    """Test command line usage of TestRock.

    It is possible to execute TestRock as command line script. Such script can be used in tox.ini
    or any other environment.
    """
    subprocess.run(
        ["python", "-c"],
        check=True) 

def test_instance_usage():
    """Test usage of instance of TestRock."""

    test_rock = TestRock(data_dir / "test_rockcraft.yaml")
    assert test_rock.get_version() == "v1.16.0_20.04_1"
    assert test_rock.get_image_name() == "sklearnserver_v1.16.0_20.04_1_amd64"
