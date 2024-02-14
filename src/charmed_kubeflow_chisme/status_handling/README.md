# Status Handling

Helpers for working with Charm Status objects

# Contents

## `check_workload_health`

Checks the workload container's health by checking the passed health check's status

Example usage:
```python
def _on_update_status(self, event):
    try:
        self.check_workload_health_check(self._container, self._container_name, self._health_check_name, self.logger)
    except ErrorWithStatus as err:
        self.model.unit.status = err.status
        self.logger.error(f"Failed to handle {event} with error: {err}")
        return
```

## `get_first_worst_error`

Parses a list of charm status objects, returning the "worst".  For example, in order of worst to best:
* BlockedStatus
* WaitingStatus
* ActiveStatus

Example usage:
```python
statuses = [
    ActiveStatus(),
    WaitingStatus("waiting"),
    BlockedStatus("blocked1"),
    BlockedStatus("blocked2")
]
worst = get_first_worst_error(statuses)
# worst is "blocked1"
```

## `set_and_log_status`

Sets the status of the charm and logs the status message.
