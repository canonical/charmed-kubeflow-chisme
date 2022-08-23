# Pebble

Helpers for working with Pebble in Charms

# Contents

## `update_layer`

Compare current layer with new layer and only update when changed.

Example usage:
```python
class Operator(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self._container_name = "container"
        self.container = self.unit.get_container(self._container_name)
        self.log = logging.getLogger(__name__)
    
     @property
    def _pebble_layer(self):
        """Return the Pebble layer for the workload."""
        return Layer(
            {
                "services": {
                    self._container_name: {
                        ...
                    }
                }
            }
        )
    
    def _on_event(self, event):
        try:
            update_layer(self._container_name, self.container, self._pebble_layer, self.log)
        except ErrorWithStatus as e:
            self.model.unit.status = e.status
            self.log.error(str(e.msg))

```
