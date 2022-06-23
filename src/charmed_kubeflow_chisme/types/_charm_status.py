# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import Type, Union

from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

# Convenience type for accepting one of the Status classes (not an instance of the class)
CharmStatusType = Type[Union[ActiveStatus, WaitingStatus, BlockedStatus, MaintenanceStatus]]
AnyCharmStatus = Union[ActiveStatus, WaitingStatus, BlockedStatus, MaintenanceStatus]
