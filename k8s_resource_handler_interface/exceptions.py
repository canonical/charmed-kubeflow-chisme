from typing import Union

from ops.model import BlockedStatus, WaitingStatus, ActiveStatus


class ErrorWithStatus(Exception):
    """Raised when an exception occurs and the raiser has an opinion on the status of the charm"""

    def __init__(
        self,
        msg: str,
        status_type: Union[ActiveStatus, WaitingStatus, BlockedStatus, None],
    ):
        super().__init__(str(msg))
        self.msg = str(msg)
        self.status_type = status_type

    @property
    def status(self):
        return self.status_type(self.msg)


class LeadershipError(ErrorWithStatus):
    """Raised when a charm should be in WaitingStatus because it is not the leader"""

    def __init__(
        self,
        msg: str = "Waiting for leadership",
        status_type: Union[
            ActiveStatus, WaitingStatus, BlockedStatus, None
        ] = WaitingStatus,
    ):
        super().__init__(msg, status_type)
