from ..types import CharmStatusType


class ErrorWithStatus(Exception):
    """Raised when an exception occurs and the raiser has an opinion on the resultant charm status
    """
    # TODO: Should this status base class just accept an instanced Status rather than msg and status_type?
    #       The msg+type feels like a chore for the user
    def __init__(self, msg: str, status_type: CharmStatusType):
        super().__init__(str(msg))
        self.msg = str(msg)
        self.status_type = status_type

    @property
    def status(self):
        return self.status_type(self.msg)
