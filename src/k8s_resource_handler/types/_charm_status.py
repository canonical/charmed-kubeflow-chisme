from typing import Type, Union
from ops.model import ActiveStatus, WaitingStatus, BlockedStatus, MaintenanceStatus

# Convenience type for accepting one of the Status classes (not an instance of the class)
CharmStatusType = Type[Union[ActiveStatus, WaitingStatus, BlockedStatus, MaintenanceStatus]]
