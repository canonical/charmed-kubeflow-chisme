# Exceptions

This is a collection of standardized Exceptions used in the Charmed Kubeflow charms.  

# Contents

## `ErrorWithStatus`

An Exception to be raised when the raiser has an opinion on the Charm status this should result in.  For example, if we have a function that checks whether a Kubernetes resource is fully deployed or still deploying, (something that likely will be resolved over time), we could do the following:

```python
from ops.model import WaitingStatus

def use_k8s_resource(resource):
    resource_status = get_resource_status(resource)
    if resource_status == "still loading, but probably will resolve over time":
        raise ErrorWithStatus(
            msg="Waiting on resource to finish deploying", 
            status_type=WaitingStatus
        )
    ...  # Else, do something with the resource

class CharmOperator(CharmBase):
    ...

    def some_handler(self):
        try:
            use_k8s_resource(self.resource)
        except ErrorWithStatus as e:
            # Catch errors that have an opinion about status and set the Charm status accordingly
            self.model.unit.status = e.status  # Sets status to WaitingStatus("Waiting on resource ...")
            self.log.info(str(e.status))  # Logs the same error message
            return
```

This makes it easy for the calling Charm to apply the proper status, and can be combined with other functions that may raise statuses to make a simpler Charm:

```python
class CharmOperator(CharmBase):
    ...

    def some_handler(self):
        try:
            use_k8s_resource(self.resource)
            do_something_that_might_raise_statused_error()
            do_something_else()
        except ErrorWithStatus as e:
            # Catch all errors that have an opinion about status, 
            # regardless of which function raised them
            self.model.unit.status = e.status
            self.log.info(str(e.status))
            return
```

## `ReplicasNotReadyError`

An opinionated subclass of `ErrorWithStatus`, raised when a Kubernetes resource does not have sufficient replicas.  Results in a `WaitingStatus`.

## `ResourceNotFoundError`

An opinionated subclass of `ErrorWithStatus`, raised when a Kubernetes resource is not found.  Results in a `BlockedStatus`.


# Usage examples
