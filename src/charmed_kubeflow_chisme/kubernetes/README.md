# Kubernetes

Helpers for interacting with Kubernetes, such as managing or inspecting Kubernetes resources.

# Contents

## KubernetesResourceHandler

### Summary

A utility for managing Kubernetes resources that are defined by templated manifests.  For example, given the template `service.yaml.j2`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ name }}
  labels:
    run: my-nginx
spec:
  type: NodePort
  ports:
  - port: {{ port }}
    targetPort: 80
    protocol: TCP
    name: http
  - port: 443
    protocol: TCP
    name: https
  selector:
    run: my-nginx
```

We can use the `KubernetesResourceHandler` to render and apply these manifests by:

```python
from charmed_kubeflow_chisme.kubernetes import KubernetesResourceHandler, create_charm_default_labels
from lightkube.core.resource import Service

render_context = {
    "name": "my-nginx",
    "port": 8080,
}

krh = KubernetesResourceHandler(
    field_manager="field_manager",
    template_files=["service.yaml.j2"],
    context=render_context,
)

# Render the manifests defined by the template_files, using the context defined by context
rendered_manifests = krh.render_manifests()
# Where rendered_manifests is a list of Lightkube.Resource objects. 

# Apply the resources defined by the manifests
krh.apply()  # This will use the manifests cached in krh._manifests

# Check the current state of these resources, returning a Charm status that describes the worst state of all objects (for example, if a single item is Blocked, this returns a BlockedStatus)
krh.compute_unit_status()
```

These helpers encapsulate the logic around looping through each template, rendering them with the context to get `Lightkube.Resource` objects, `apply`ing them to the Kubernetes Cluster in a safe order, etc.  

If we plan on managing these resources over time, we can provide the optional `labels` and `resource_types` arguments:
* `labels`: a set of labels used to identify the resources deployed by this resource handler, even during separate charm executions.  Use the included `create_charm_default_labels` for a standard set of labels.
* `resource_types`: a set of `Lightkube.Resource` types that are expected to be deployed by this resource handler.

By adding `labels` and `resource_types`, we can manage deployed resources including through reconciliation and deletion.  For example, if we have a `Deployment` and a `Service` that are both deployed by this resource handler, we can provide `resource_types={Deployment, Service}` to the constructor.  This will allow us to later get all resources deployed by this resource handler by querying the cluster for all resources with the labels defined in `labels` and of type `Deployment` or `Service`.

For example:

```python
krh = KubernetesResourceHandler(
    field_manager="field_manager",
    template_files=["service.yaml.j2"],
    context=render_context,
    labels=create_charm_default_labels(
        application_name="my-application", model_name="my-model", scope="my-scope"
    ),
    resource_types={Service},
)

# Get the resources we currently have deployed
# (this uses the labels and resource_types defined in the constructor.  See the docstring for more details)
current_resources = krh.get_deployed_resources()
# Returns []

# Create our Service from before
krh.apply()

# Returns a list with our `my-nginx` Service
current_resources = krh.get_deployed_resources()

# Changes the name of the object, meaning we need to delete the old and create a new one
new_render_context = {
    "name": "my-nginx2",
    "port": 8081,
}
krh.context = new_render_context

# Reconcile removes the old object because it is not in the current manifests, and creates a new one.
krh.reconcile()

# Returns a list with our new `my-nginx2` Service
current_resources = krh.get_deployed_resources()

# And later, we can delete the resources
krh.delete()
# Where this would delete anything that was created by this resource handler, past or present. 
```

### Recommended usage patterns

The `KubernetesResourceHandler` can be used to manage one or more YAML templates, but it does not need to be the single monolith that manages all kubernetes resources in a charm.  For example, if you have a `service.yaml.j2`, `deployment.yaml.j2`, and `rbac.yaml.j2` which define resources that are always rendered and deployed together, it likely makes sense to use a single `KubernetesResourceHandler` for all three for convenience.  However, if you commonly need to update the `deployment.yaml.j2` without modifying the others, it might make more sense instantiate separate `KubernetesResourceHandler` objects, for the different files or more fine-grained groups of files.  

It is often convenient to define common `KubernetesResourceHandler` objects that are used by multiple hooks up front in a charm, but there is nothing wrong with instantiating smaller helper `KubernetesResourceHandler` objects when you need them too (for example, when a specific function wants to manipulate a small subset of yaml files).

## `check_resources`

A generic function for checking the state of resources in Kubernetes.  Returns a boolean indicating whether all resources are ok, as well as a list of any errors.  For example:

```python

status, errors = check_resources(lightkube_resources)

# where:
# * status==True and len(errors)==0 if all resources are ok
# * status==False and len(errors)>0 if any resources are not ok
```

