# Charmed Kubeflow Chisme

Chisme: a Spanish word for gossip, or a story worth telling to your friends.  

This repository is for chisme within the Charmed Kubeflow team's codebase - it is a collection of helpers for use in 
both the Charmed Operators maintained by the [Charmed Kubeflow](ckf) team as well as anyone else who benefits from them.

# Contents

* [Exceptions](./src/charmed_kubeflow_chisme/exceptions/README.md): A collection of standard Exceptions for use when writing charms.
* [Kubernetes](./src/charmed_kubeflow_chisme/kubernetes/README.md): Helpers for interacting with Kubernetes
* [Lightkube](./src/charmed_kubeflow_chisme/lightkube/README.md): Helpers specific to using or extending [Lightkube](lightkube-rtd)
* [Status Handling](./src/charmed_kubeflow_chisme/status_handling/README.md): Helpers for working with Charm Status objects
* [Types](./src/charmed_kubeflow_chisme/types/README.md): Reusable typing definitions, useful for adding type hints
* [Pebble](./src/charmed_kubeflow_chisme/pebble/README.md): Helpers for managing pebble when writing charms

[ckf]: https://charmed-kubeflow.io/
[lightkube-rtd]: https://lightkube.readthedocs.io/en/latest/

# Publishing to PyPi

To publish a new release to Pypi:
1. Update [setup.cfg](https://github.com/canonical/charmed-kubeflow-chisme/blob/main/setup.cfg#L3) to the new version 
   and commit it to the repo via a completed PR
2. Apply local git tag according to the format `vX.X.X` (semantic versioning) on the main branch
3. Push tag to the repo. Example: `git push origin v0.0.8`
4. GitHub Action will create a new release on GitHub
5. Edit release via GitHub UI and click publish
6. GitHub Action will automatically publish the same commit to PyPi repository 
