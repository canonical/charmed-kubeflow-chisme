# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

class UnitErrorStatusWithMessage(Exception):  # noqa: N818
    """Raised when the unit should be in ErrorStatus with a message to show in juju status."""

    def __init__(self, msg: str):
        __module__ = None
        super().__init__(str(msg))
        self.msg = str(msg)
