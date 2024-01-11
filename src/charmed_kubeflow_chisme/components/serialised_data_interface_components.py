# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
"""Reusable Components for handling SerializedDataInterface-backed relations."""
import logging
from typing import Any, Callable, List, Optional, Union

from jsonschema import ValidationError
from ops import ActiveStatus, BlockedStatus, CharmBase, StatusBase, WaitingStatus
from serialized_data_interface import (
    NoCompatibleVersions,
    NoVersionsListed,
    SerializedDataInterface,
    get_interface,
)
from serialized_data_interface.errors import UnversionedRelation

from charmed_kubeflow_chisme.components import Component
from charmed_kubeflow_chisme.exceptions import ErrorWithStatus

logger = logging.getLogger(__name__)

NEEDS_EXACTLY_N_RELATED_APPS_ERROR = (
    "Expected data from exactly {related_applications_expected} related applications - got "
    "{n_related_applications}."
)

TOO_FEW_RELATED_APPS_ERROR = (
    "Expected data from at least {minimum_related_applications} related applications - got "
    "{n_related_applications}."
)

TOO_MANY_RELATED_APPS_ERROR = (
    "Expected data from at most {maximum_related_applications} related applications - got "
    "{n_related_applications}."
)


class SdiRelationDataReceiverComponent(Component):
    """Wraps an SDI-backed relation that receives data."""

    def __init__(
        self,
        charm: CharmBase,
        name: str,
        relation_name,
        *args,
        inputs_getter: Optional[Callable[[], Any]] = None,
        minimum_related_applications: Optional[int] = 1,
        maximum_related_applications: Optional[int] = 1,
        **kwargs,
    ):
        """Wraps an SDI-backed relation that receives data, validating basic requirements.

        Known issues: due to limitations in the operator framework described in
        https://github.com/canonical/kubeflow-dashboard-operator/issues/124 and related issues,
        updates on relation-broken events may incorrectly report the broken application still being
        related to this charm.  This will be resolved on the next charm reconcile event or
        update-status.

        Args:
            charm: (from ops.Object's `framework` parameter) Charm that will be the parent of the
                   Charm framework events related to this Component.
                   Note that this can also accept a Framework object, although this is probably
                   useful only in unit tests.
            name: Unique name of this instance of the class.  This is used as the ops.Object key
                  argument, as well as for some status/debug printing.
            relation_name: the name of the relation handled by this Component
            inputs_getter: (optional) a function that returns an object with inputs that can be
                           used in the component.  Needed only when instantiating objects that
                           required data that is not available until later during runtime, like
                           passing data from a one Component to another.
            minimum_related_applications: the minimum number of relations required for this
                                          Component to be Active.  Component will be Blocked if
                                          this is not satisfied.
            maximum_related_applications: the maximum number of relations required for this
                                          Component to be Active.  Component will be Blocked if
                                          this is not satisfied.
        """
        super().__init__(charm, name, *args, inputs_getter=inputs_getter, **kwargs)
        self._relation_name = relation_name
        self._minimum_related_applications = minimum_related_applications
        self._maximum_related_applications = maximum_related_applications

        self._events_to_observe = [
            self._charm.on[self._relation_name].relation_changed,
            self._charm.on[self._relation_name].relation_broken,
        ]

    def get_data(self) -> Union[List[dict], dict]:
        """Returns the data in this relation, raising a ErrorWithStatus if data is not as expected.

        Validation asserts that there is data for the number of apps expected, and that the data
        provided fits the expected schema.
        """
        interface = self.get_interface()

        if interface is None:
            if self._minimum_related_applications > 0:
                if self._minimum_related_applications == self._maximum_related_applications:
                    error_msg = NEEDS_EXACTLY_N_RELATED_APPS_ERROR.format(
                        related_applications_expected=self._minimum_related_applications,
                        n_related_applications=0,
                    )
                else:
                    error_msg = TOO_FEW_RELATED_APPS_ERROR.format(
                        minimim_related_applications=self._minimum_related_applications,
                        n_related_applications=0,
                    )
                raise ErrorWithStatus(error_msg, BlockedStatus)

        try:
            unpacked_data = list(interface.get_data().values())
        except ValidationError as val_error:
            # Validation in .get_data() ensures if data is populated, it matches the schema and is
            # not incomplete
            msg = f"Got ValidationError when interpreting data on relation {self._relation_name}: {val_error}"
            raise ErrorWithStatus(msg, BlockedStatus) from val_error

        self.validate_number_of_relations(unpacked_data)

        # If relation supports exactly 1 relation, return just that relation's data.  Else, return
        # as a list.
        if self._minimum_related_applications == self._maximum_related_applications:
            return unpacked_data[0]
        else:
            return unpacked_data

    def get_interface(self) -> Optional[SerializedDataInterface]:
        """Returns the SerializedDataInterface object for this interface."""
        return get_sdi_interface(self._charm, self._relation_name)

    def get_status(self) -> StatusBase:
        """Returns the status of this relation.

        Use this in the charm to inspect the state of the relation and its data.

        Will return:
            * BlockedStatus: if we have no compatible versions on the relation, or no related
                             app
            * WaitingStatus: if we have not yet received a version from the opposite relation
            * ActiveStatus: if:
                * nothing is related to us (as there is no work to do)
                * we have one or more relations, and we have sent data to all of them
        """
        try:
            # If we successfully get data, we are active
            self.get_data()
        except ErrorWithStatus as err:
            return err.status

        return ActiveStatus()

    def validate_number_of_relations(self, data: List[dict]):
        """Asserts we have the correct number of related applications.

        Raises ErrorWithStatus if the number is not correct.
        """
        if len(data) < self._minimum_related_applications:
            if self._minimum_related_applications == self._maximum_related_applications:
                error_msg = NEEDS_EXACTLY_N_RELATED_APPS_ERROR.format(
                    related_applications_expected=self._minimum_related_applications,
                    n_related_applications=len(data),
                )
            else:
                error_msg = TOO_FEW_RELATED_APPS_ERROR.format(
                    minimim_related_applications=self._minimum_related_applications,
                    n_related_applications=len(data),
                )
            raise ErrorWithStatus(error_msg, BlockedStatus)

        if len(data) > self._maximum_related_applications:
            error_msg = TOO_MANY_RELATED_APPS_ERROR.format(
                maximum_related_applications=self._maximum_related_applications,
                n_related_applications=len(data),
            )
            raise ErrorWithStatus(error_msg, BlockedStatus)


class SdiRelationBroadcasterComponent(Component):
    """Wraps an SDI-backed relation that sends the same data to all related applications."""

    def __init__(
        self,
        charm: CharmBase,
        name: str,
        relation_name,
        data_to_send: dict,
        *args,
        inputs_getter: Optional[Callable[[], Any]] = None,
        **kwargs,
    ):
        """Wraps an SDI-backed relation that sends the same data to all related applications.

        Note that as SDI relations communicated on application data, this only sends data if this
        charm is the leader.

        Args:
            charm: (from ops.Object's `framework` parameter) Charm that will be the parent of the
                   Charm framework events related to this Component.
                   Note that this can also accept a Framework object, although this is probably
                   useful only in unit tests.
            name: Unique name of this instance of the class.  This is used as the ops.Object key
                  argument, as well as for some status/debug printing.
            relation_name: the name of the relation handled by this Component
            data_to_send: dict of data to be sent to every related application
            inputs_getter: (optional) a function that returns an object with inputs that can be
                           used in the component.  Needed only when instantiating objects that
                           required data that is not available until later during runtime, like
                           passing data from a one Component to another.
        """
        super().__init__(charm, name, *args, inputs_getter=inputs_getter, **kwargs)
        self._relation_name = relation_name
        self._events_to_observe = [
            self._charm.on[self._relation_name].relation_created,
            self._charm.on[self._relation_name].relation_changed,
        ]
        self._data_to_send = data_to_send

    def _configure_app_leader(self, event):
        """Send data to all related applications if we are the leader."""
        interface = self.get_interface()
        if interface is None:
            return

        interface.send_data(data=self._data_to_send)

    def get_interface(self) -> Optional[SerializedDataInterface]:
        """Returns the SerializedDataInterface object for this interface."""
        return get_sdi_interface(self._charm, self._relation_name)

    def get_status(self) -> StatusBase:
        """Returns the status of this relation.

        Use this in the charm to inspect the state of the relation and its data.

        Will return:
            * BlockedStatus: if any related app shows a "no compatible versions" error
            * WaitingStatus: if any related app has not yet sent its version data
            * ActiveStatus: if:
                * nothing is related to us (as there is no work to do)
                * we have one or more relations, and we have sent data to all of them
        """
        required_attributes = self._data_to_send.keys()
        unknown_error_message = (
            f"Caught unknown exception while checking readiness of {self._relation_name}: "
        )

        try:
            interface = self.get_interface()
        except ErrorWithStatus as err:
            return err.status

        if interface is None:
            # Nothing is related to us, so we have nothing to send out.  Relation is Active
            return ActiveStatus()

        try:
            # We check whether we've sent, on our application side of the relation, the required
            # attributes
            interface_data_dict = interface.get_data()
            this_apps_interface_data = interface_data_dict[
                (self.model.get_relation(self._relation_name), self._charm.app)
            ]

            missing_attributes = []
            # TODO: This could validate the data sent, not just confirm there is something sent.
            #  Would that be too much?
            for attribute in required_attributes:
                if not (
                    attribute in this_apps_interface_data
                    and this_apps_interface_data[attribute] is not None
                    and this_apps_interface_data[attribute] != ""
                ):
                    missing_attributes.append(attribute)

            if missing_attributes:
                msg = (
                    f"Relation is missing attributes {missing_attributes} that we send out."
                    f"  This likely is a transient error but if it persists, there could be"
                    f" something wrong."
                )

                return WaitingStatus(msg)

            return ActiveStatus()
        except Exception as err:
            logging.info(unknown_error_message)
            return BlockedStatus(str(unknown_error_message + str(err)))


def get_sdi_interface(charm: CharmBase, relation_name: str):
    """Returns an interface from an SDI relation, raising ErrorWithStatus on common error cases."""
    try:
        interface = get_interface(charm, relation_name)
        # TODO: These messages should be tested and cleaned up
    except (NoVersionsListed, UnversionedRelation) as err:
        raise ErrorWithStatus(str(err), WaitingStatus) from err
    except NoCompatibleVersions as err:
        raise ErrorWithStatus(str(err), BlockedStatus) from err
    except Exception as err:
        raise ErrorWithStatus(f"Caught unknown error: '{str(err)}'", BlockedStatus) from err

    return interface
