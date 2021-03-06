# Kubernetes

Helpers for interacting with Kubernetes, such as managing or inspecting Kubernetes resources.

# Contents

## KubernetesResourceHandler

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

## `check_resources`

A generic function for checking the state of resources in Kubernetes.  Returns a boolean indicating whether all resources are ok, as well as a list of any errors.  For example:

```python

status, errors = check_resources(lightkube_resources)

# where:
# * status==True and len(errors)==0 if all resources are ok
# * status==False and len(errors)>0 if any resources are not ok
```
