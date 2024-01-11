# Defining Execution Order in a `CharmReconciler`

*********************TODO: REWORD TITLE?????

Typically, a charm has a mix of functionality.  For example, it might:
1. manage a Pebble container
2. allow applications to relate to it on `relation-1`
3. send data about the Pebble container to the related application on `relation-1` 
4. allow applications to relate to it on `relation-2`
5. create a Kubernetes resource for every related application on `relation-2`

Often, these are executed in sequence, where if any of them fails to complete the charm is put into `BlockedStatus` or `ErrorStatus`.  Sometimes this is desirable, but often it isn't.  For example, steps (4) and (5) of the above charm do not depend on steps (1)-(3), and it might be desirable for (4) and (5) to successfully execute even if other functionality is `Blocked`.  

A goal of the `CharmReconciler` is to let charm authors define charms that have any mix of dependencies between `Components`, and for the resulting charm to compute as much as possible while clearly logging what is impeding progress.  The `status` of the entire charm is aggregated from the status of all pieces of the charm.

# Defining Execution Order in a `CharmReconciler`

`Components` are added to a `CharmReconciler` using `.add()`:

```python
class CharmReconciler:
	def add(
        self,
        component: Component,
        depends_on: Optional[List[ComponentGraphItem]] = None,
    ) -> ComponentGraphItem:
        """Add a component to the graph.

        Args:
            component: the Component to add to this execution graph
            depends_on: the list of registered ComponentGraphItems that this Component
                        depends on being Active before it should run.
        """
```

Dependency between `Components` is defined through the `depends_on` argument.  `depends_on` defines which other `Components` must be executed and ready (`ActiveStatus`) before executing this one. [^1].  The `CharmReconciler` will execute `Components` one at a time until:

* all `Components` have executed exactly once
* all remaining `Components` have at least one non-active dependency

Looking at the charm from the previous section, we can write it as (with configuration details truncated by `...`):

```python
class MyCharm(CharmBase):
  def __init__(self):
    self.charm_reconciler = CharmReconciler()

    self.pebble_component = self.charm_reconciler.add(PebbleServiceComponent(...))
    # Monitors related applications on relation_1 
    self.relation_1_component = self.charm_reconciler.add(
    	Relation1Component(...),
    	depends_on=[self.pebble_component]
    )

    self.relation_2_component = self.charm_reconciler.add(Relation2Component(...))
    self.kubernetes_resource_component = self.charm_reconciler.add(
    	KubernetesResourceComponent(...),
    	depends_on=[self.relation_2_component]
    )

    self.charm_reconciler.install_default_event_handlers()
```

This defines a charm that will:
* always try to configure `self.pebble_component`.  If this is successful and goes to active, it will then try to configure `self.relation_2_component`
* always try to configure `self.relation_2_component`.  If this is successful and goes to active, it will then try to configure `self.kubernetes_resource_component`

This means that an error in `self.pebble_component` (for example, a pebble container that does not go active due to an incorrect image) will not block configuring `self.kubernetes_resource_component`.  

[^1]: This document talks about working with `Components`, but `depende_on` accepts and `.add()` returns `ComponentGraphItem`s, not `Component`s.  A `ComponentGraphItem` wraps a `Component` with extra information about dependencies between `Components`.  In hindsight, this probably shouldn't be part of the public api and is confusing.  Suggestions welcome on how to make this more intuitive.  Maybe this is information the `CharmReconciler` should keep internally, but then externally it just interacts with `Components`?

**TODO:** show examples of how the charm status and debug logs look for different scenarios
