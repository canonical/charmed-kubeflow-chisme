# Reusable Charm Components

An encapsulation for any piece of logic (a `Component`) that is used in a Charm.

# Summary

These are tools for implementing a holistic, reconcile-style charm (one that typically reconciles all aspect of the charm on major events like `config-changed`, `install`, etc.), and for making resuable pieces of logic to be executed by that type of charm.

Included here are:
* the `Component` abstraction, which defines the minimum API that any piece of Charm logic should implement
* the `CharmReconciler`, a reusable execution loop that executes one or more `Component` in a specified order.  
* several reusable `Components` (`KubernetesResourceComponent`, `PebbleServiceComponent`, etc) that can be used for Charm development

# Concepts

## Reconcile-style Charms

The term "reconcile-style charm" here means a charm that, for any major Juju event:
* observes the current input state, such as config values, relation data, etc.
* applies the desired output state for the things it manages, such as updating Pebble services in a container or deploying Kubernetes resources to the state they should be based on the current inputs

This reconciliation is typically done holistically on everything the Charm manages, rather than in an imperitive style based only on what this current event has indicated.  A similar concept is discussed as [Deltas vs holistic charming](https://discourse.charmhub.io/t/deltas-vs-holistic-charming/11095) in Discourse.  

A typical charm for this sort of pattern could look like:

```python
class MyCharm(CharmBase):
  def __init__(self):
    for event in [
      self.on.install,
      self.on.config_changed,
      self.on.containerA_pebble_ready,
      self.on[relationX].relation_changed,
      self.on[relationY].relation_changed, 
      ...
    ]:
      self.framework.observe(event, self.reconcile)

  def reconcile(self, event):
    self._get_data_from_relation_X(event)
    self._send_data_to_relation_Y(event)
    self._deploy_kubernetes_resource_using_relation_X_data(event)
    self._update_container_a(event)
    ...
```

where we run the same `reconcile()` event handler for `install`, `config-changed`, etc., and `reconcile()` might be a series of helpers each handling different functions of the Charm.

## `Component`

`Component` is an abstraction that represents a single piece of logic in a Charm, for example configuring a Pebble container or sending data to a relation.   In the example from [Reconcile-style Charms](#Reconcile-style-Charms), the helpers in `reconcile()` would each be a good candidate to be a `Component`.  Each component implements:

* `.configure_charm()`: does the work of this `Component` (configures a Pebble container, deploys a resource, etc.)
* `.remove()`: does any work that should be done to remove this `Component` during a Charm's `remove` event
* `.get_status()`: computes the Status of this `Component` given the current state, returning a `ops.model.StatusBase` (like `ActiveStatus`, `BlockedStatus`, etc.)

The intent of the `Component` is to define all aspects of managing this particular job the Charm in a predictable way so that several `Components` can be composed to form a Charm.  

**TODO: mention status more.  How we represent success via charm status, and it matters for further execution**

## `CharmReconciler`

`CharmReconciler` is a reusable reconcile function for executing one or more `Component`s.  `Components` are `CharmReconciler.add()`ed to bring them in scope, and then the `CharmReconciler` provides standard event handlers for some Charm events:
* for Charm reconcile events (typically  `install`, `config-changed`, `*-pebble-ready`, some relation events), `.execute_components(event)` executes all `Components` in a user-defined order and updates the Charm's status based on their results
* for the `remove` event, `.remove_components(event)` runs `Component.remove()` for all `Components`
* for the `update-status` event, `.update_status(event)` computes the status of each `Component` and updates the Charm's status

Typically, these handlers can replace existing ones for these events, but they could be used in combination with other custom code within the Charm.  

Rewriting the reconcile-style charm example [above](#Reconcile-style-Charms) using `CharmReconciler` gives:

```python
class MyCharm(CharmBase):
  def __init__(self):
    self.charm_reconciler = CharmReconciler()

    self.relation_x_component = self.charm_reconciler.add(GetDataFromRelationXComponent)
    self.relation_y_component = self.charm_reconciler.add(SendDataToRelationYComponent)
    self.k8s_component = self.charm_reconciler.add(DeployKubernetesResourceComponentUsingRelationXData, depends_on=self.relation_x_component)
    self.container_a_component = self.charm_reconciler.add(UpdateContainerAComponent)

    # Replaces all self.framework.observe statements above
    self.charm_reconciler.install_default_event_handlers()
```

where `k8s_component`'s `depends_on=self.relation_x_component` establishes that `k8s_component` can only successfully execute after `relation_x_component` has succeeded (gone to `ActiveStatus`).  

# How-to Guides

TODO: Explain both Component and CharmReconciler

# UNUSED TEXT / TODO

`execute_components()` executes `Components` in the order defined by the dependencies between `Components`, allowing for `ComponentB` to depend on and need data from `ComponentA`, while `ComponentC`

To control the order in which `execute_components()` executes `Components`, dependencies can be defined:

```python
class MyCharm(CharmBase):
  def __init__()
```


* multistatus/prioritizer/aggregation
* something showing dependency

