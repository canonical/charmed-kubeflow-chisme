# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


class GenericCharmRuntimeError(Exception):
    """Raised when the unit should be in ErrorStatus with a message to show in juju status.

    This exception can be used in the charm code to indicate that there is an issue in runtime
    caused by any type of error.

    A typical usage might be:

    ```python
    from charmed_kubeflow_chisme.exceptions import GenericCharmRuntimeError

    try:
        some_function()
    except SomeErrorOfTheFunction as e:
        raise GenericCharmRuntimeError("Some function failed because x and y") from e
    """

    __module__ = None

    def __init__(self, msg: str, *args):
        super().__init__(str(msg), *args)
        self.msg = str(msg)
