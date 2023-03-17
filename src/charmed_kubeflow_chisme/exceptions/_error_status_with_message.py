# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


class UnitErrorStatusWithMessage(Exception):  # noqa: N818
    """Raised when the unit should be in ErrorStatus with a message to show in juju status."""

    __module__ = None

    def __init__(self, msg: str):
        super().__init__(str(msg))
        self.msg = str(msg)
