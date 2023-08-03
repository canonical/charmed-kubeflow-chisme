# Upgrades when using `CharmReconciler`

This guide describes how to define an upgrade procedure for a charm that uses the `CharmReconciler` and charm `Components`. 

## How charm upgrades work in general

When a charm is upgraded (refreshed from one version to another), the following occurs ([reference](https://juju.is/docs/sdk/upgrade-charm-event)):
1. old version of the charm receives no indication of the upgrade (it receives a stop `stop` event, but nothing specifically identifies this stop as upgrade related)
2. new charm is deployed after the old version has been removed
3. new charm receives an `upgrade-charm` event
4. new charm receives a `config-changed` event (this is guaranteed to fire after `upgrade-charm`)
5. (TODO: need to confirm) the new version of the charm receives pebble-ready events as pebble becomes ready on the new charm

The `upgrade-charm` event is meant for doing any work that is unique to upgrading a charm's state from the old version's style to that that the current charm requires.  For example, migrating relation data from an old schema to a new one.  

Depending on charm design, handling the `upgrade-charm` event may not be necessary.  For example, if the relation handler always overwrites the entire databag on every `config-changed` event, you do not need to do special handling during the `upgrade-charm` event.  But if your handler only incrementally changes data, or you need to clean up data from the previous style, you do need an `upgrade-charm` handler for that migration. 

## How charm upgrades work for a charm that uses the `CharmReconciler`

`CharmReconciler` is a reusable reconcile function, meant to handle reconcile-style events (`config-changed`, `*-pebble-ready`, etc.).  Nothing in `CharmReconciler` or its `Components` explicitly handle upgrades.  

In cases where a reconcile event will do everything needed in the charm upgrade process, no additional event handling is needed to support upgrades.  The upgrade lifecycle from above will be handled such that:

2. new charm is deployed
3. new charm receives an `upgrade-charm` event but **does not handle it**
4. new charm receives a `config-changed` event that is handled by `CharmReconciler`, reconciling the charm

In cases where special logic is required for migrating part of the charm, there are two options:

1. include migration logic in the relevant `Component` (for example, in `Component._configure_unit()`)
2. add additional event handlers in the charm `self.framework.observe()` the upgrade event

Option (1) is good when the actions needed for migration are inexpensive and idempotent, for example an `if` statement that looks at a relation's data, if it sees keys that were in the old schema, removes them and migrates the data.  Using this approach will make the regular `config-changed` behaviour of your charm implicitly do upgrades and requires no additional event handling.

Option (2) is good when option (1) is not suitable.  In this case, you can write any charm code needed to do work on the `upgrade-charm` event.  This code is written like any regular charm event handler, not as part of the `CharmReconciler`.  

An example of option (2) would be:

```python
class MyCharm(CharmBase):
    def __init__(self):
        ...
        
        # Handle charm upgrade
        self.framework.observe(self.on.upgrade_charm, self.upgrade_charm)

    def upgrade_charm(self, _: BoundEvent):
        """Handler for an upgrade-charm event.

        This handler should do anything required for upgrade that is not already covered by a
        regular Component in self.charm_reconciler.
        """
        do_upgrade()
```
