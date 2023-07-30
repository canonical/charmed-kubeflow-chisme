# How to Author a `Component`

Charm Components are encapsulated pieces of Charm functionality, for example how to update a Pebble container or send data to all units on a Relation.  The `Component` class defines the interface that these encapsulated pieces must provide.

To create a custom `Component`, extend the `Component` class (or one of the included subclasses, such as `KubernetesComponent`) and implement the methods as defined in the following sections.  

## Defining what a `Component` does during Charm reconciliation

What a `Component` does during a reconcile event (any event handled by `CharmReconciler.execute_components()`) is defined through one or more of the following methods:

```python
class MyComponent(Component):
    def _configure_unit(self, event):
        """Executes everything this Component should do for every Unit.
        """

    def _configure_app_leader(self, event):
        """Execute everything this Component should do at the Application level for leaders.
        """

    def _configure_app_non_leader(self, event):
        """Execute everything this Component should do at the Application level for non-Leaders.
        """
```

Depending on the needs of the `Component`, any or all of these can be implemented.  For example, a `Component` for a Pebble container likely needs to do work on every unit and should use `_configure_unit`, whereas Kubernetes resources that are created once for the application shoud use `_configure_app_leader`.  

Implementation detail: `CharmReconciler.execute_components()` executes `Component.configure_charm()`, which then delegates execution to the `_configure_*` methods.  If you need behaviour not covered by the standard cases, you can directly override `Component.configure_charm()` to implement what your `Component` needs. 

## Defining what a `Component` does during Removal

For `Components` that should do something on `remove` events, implement `Component.remove()`:

```python
    def remove(self, event):
        """Removes everything this Component should when handling a `remove` event."""
```

For example, a `KubernetesComponent` can implement a `Component.remove()` that tries to remove any resources it created.

Note that `CharmReconciler` executes `Component.remove()` in any order, not the order defined by `depends_on`.  `Component.remove()` should catch and log any non-fatal errors for the removal event - any error raised from `Component.remove()` may put the charm into error and prevent removal.  

## How to report the status of your `Component`

Every `Component` must implement `Component.get_status() -> StatusBase`:

```python
    @abstractmethod
    def get_status(self) -> StatusBase:
        """Returns the status of this Component.

        Override this method to implement the logic that establishes your Component
        status (eg: if I have data from my relation, I am Active)
        """
```

This method should:
* assess the current state of the charm with respect to what this `Component` implements
* return a standard ops `StatusBase` (`ActiveStatus`, `BlockedStatus`, ...) representing the status of *this component of the charm*.  

The return of `Component.get_status()` indicates whether this part of the charm is operational.  The `CharmReconciler` aggregates this with the status from the other `Components` in the charm to determine the entire charm's status.  

For example, a `Component` that manages a relation required by this charm might read the data provided on the relation and return:
* `BlockedStatus("Needs required relation X")` if we do not have the required related applications
* `WaitingStatus("Waiting for required data from related application on relation X")` if we have related applications, but they have not yet sent data
* `ActiveStatus()` if we have the required data our charm needs

An implementation of `Component.get_status()` should be *holistic* and require only the state which can be observed from the charm during execution.  For example, it should look at all the data on a relation and decide whether any is missing, rather than look at an incremental change in the data.  This is because `Component.get_status()` may be fired throughout the charm's lifecycle, such as after or even before `Component.configure_charm()`.  

## Handling non-standard events

`CharmReconciler` by default handles `install` and `config-changed`, but some `Components` need to handle additional events (for example, a `Component` managing a Pebble container should execute on its own `pebble-ready` event).  A `Component` can request the `CharmReconciler` execute on additional events by defining its `events_to_observe`:

TODO: Add example.  Until then, see the `PebbleServiceComponent`

TODO: This should be changed to have a better setter function, not just an override