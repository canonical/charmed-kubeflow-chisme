# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from ..types import CharmStatusType


class ErrorWithStatus(Exception):  # noqa: N818
    """Base class of exceptions for when the raiser has an opinion on the resulting charm status.

    Commonly used when the parent charm wants to catch any ErrorWithStatus Exceptions and set its
    unit status accordingly.
    """

    def __init__(self, msg: str, status_type: CharmStatusType):
        super().__init__(str(msg))
        self.msg = str(msg)
        self.status_type = status_type

    def __eq__(self, other):
        """Defines equality between ErrorWithStatus objects."""
        if isinstance(other, self.__class__):
            return self.msg == other.msg and self.status == other.status

    @property
    def status(self):
        """Returns an instance of self.status_type, instantiated with this exception's message."""
        return self.status_type(self.msg)
