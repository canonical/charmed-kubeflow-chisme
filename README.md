# Charmed Kubeflow Chisme

Chisme: a Spanish word for gossip, or a story worth telling to your friends.  

This repository is for chisme within the Charmed Kubeflow team's codebase - it is a collection of helpers for use in 
both the Charmed Operators maintained by the [Charmed Kubeflow](ckf) team as well as anyone else who benefits from them.

# Contents

* [Exceptions](./src/k8s_resource_handler/exceptions/README.md): A collection of standard Exceptions for use when writing charms.
* [Kubernetes](./src/k8s_resource_handler/kubernetes/README.md): Helpers for interacting with Kubernetes
* [Lightkube](./src/k8s_resource_handler/lightkube/README.md-dir): Helpers specific to using or extending [Lightkube](lightkube-rtd)
* [Status Handling](./src/k8s_resource_handler/status_handling/README.md): Helpers for working with Charm Status objects
* [Types](./src/k8s_resource_handler/types/README.md): Reusable typing definitions, useful for adding type hints

[ckf]: https://charmed-kubeflow.io/
[lightkube-rtd]: https://lightkube.readthedocs.io/en/latest/
