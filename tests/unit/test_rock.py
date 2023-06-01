# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import subprocess
from pathlib import Path

from charmed_kubeflow_chisme.rock import CheckRock

data_dir = Path(__file__).parent.joinpath("data")


def test_rock_cli_usage():
    """Test command line usage of CheckRock.

    It is possible to execute CheckRock as command line script. Such script can be used in tox.ini
    or any other environment.
    """
    subprocess.check_output(
        [
            "python",
            "-c",
            f"'from charmed_kubeflow_chisme.rock import CheckRock; print(CheckRock(\"{data_dir}/test_rockcraft.yaml\").get_version())'",
        ],
    )


def test_rock_instance_usage():
    """Test usage of instance of CheckRock."""
    check_rock = CheckRock(data_dir / "test_rockcraft.yaml")
    assert check_rock.get_version() == "v1.16.0_20.04_1"
    assert check_rock.get_image_name() == "sklearnserver_v1.16.0_20.04_1_amd64"
