# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import subprocess


def fire_update_status_to_unit(unit_name: str, model_name: str):
    """Fire an update-status to unit_name unit.

    This was generated using `jhack fire foo/0 update-status --dry-run`.

    Args:
        unit_name: The name of the unit to fire an update_status to e.g. foo/0
        model_name: The name of the model where unit is deployed
    """
    subprocess.Popen(
        [
            "juju",
            "ssh",
            unit_name,
            "/usr/bin/juju-exec",
            "-u",
            unit_name,
            "JUJU_DISPATCH_PATH=hooks/update-status",
            f"JUJU_MODEL_NAME={model_name}",
            f"JUJU_UNIT_NAME={unit_name}",
            "./dispatch",
        ]
    )
