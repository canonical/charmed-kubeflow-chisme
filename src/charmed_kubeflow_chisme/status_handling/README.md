# Status Handling

Helpers for working with Charm Status objects

# Contents

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
