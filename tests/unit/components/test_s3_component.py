# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

import pytest
from fixtures import DummyCharm  # noqa: F401
from ops import ActiveStatus, BlockedStatus
from ops.testing import Harness

from charmed_kubeflow_chisme.components.s3_component import S3RequirerComponent

RELATION_NAME = "s3-credentials"

METADATA_WITH_S3_RELATION = f"""
name: test-charm
requires:
  {RELATION_NAME}:
    interface: s3
"""


@pytest.fixture()
def harness():
    harness = Harness(DummyCharm, meta=METADATA_WITH_S3_RELATION)
    harness.begin()
    return harness


@pytest.fixture()
def s3_component(harness):
    """Returns an S3RequirerComponent with a mocked S3Requirer."""
    with patch("charmed_kubeflow_chisme.components.s3_component.S3Requirer", MagicMock()):
        component = S3RequirerComponent(
            charm=harness.charm,
            name="s3-component",
            relation_name=RELATION_NAME,
        )
    return component


@pytest.fixture()
def s3_component_optional(harness):
    """Returns an optional S3RequirerComponent with a mocked S3Requirer."""
    with patch("charmed_kubeflow_chisme.components.s3_component.S3Requirer", MagicMock()):
        component = S3RequirerComponent(
            charm=harness.charm,
            name="s3-component-optional",
            relation_name=RELATION_NAME,
            is_optional=True,
        )
    return component


class TestS3RequirerComponentGetStatus:
    def test_active_when_optional_and_relation_absent(self, s3_component_optional):
        """When is_optional=True and no relation is present, status should be Active."""
        status = s3_component_optional.get_status()
        assert isinstance(status, ActiveStatus)

    def test_blocked_when_required_and_relation_absent(self, s3_component):
        """When is_optional=False and no relation is present, status should be Blocked."""
        status = s3_component.get_status()
        assert isinstance(status, BlockedStatus)
        assert RELATION_NAME in status.message

    def test_active_when_relation_present_with_data(self, harness, s3_component):
        """When the relation is present and all required fields are available, status is Active."""
        harness.add_relation(RELATION_NAME, "remote-app")
        s3_component.s3_client.get_storage_connection_info.return_value = {
            "access-key": "key",
            "secret-key": "secret",
        }
        status = s3_component.get_status()
        assert isinstance(status, ActiveStatus)

    def test_blocked_when_relation_present_but_no_data(self, harness, s3_component):
        """When the relation is present but returns no data, status should be Blocked."""
        harness.add_relation(RELATION_NAME, "remote-app")
        s3_component.s3_client.get_storage_connection_info.return_value = None
        status = s3_component.get_status()
        assert isinstance(status, BlockedStatus)
        assert RELATION_NAME in status.message

    def test_blocked_when_relation_present_but_data_incomplete(self, harness, s3_component):
        """When the relation is present but required fields are missing, status is Blocked."""
        harness.add_relation(RELATION_NAME, "remote-app")
        s3_component.s3_client.get_storage_connection_info.return_value = {"access-key": "key"}
        status = s3_component.get_status()
        assert isinstance(status, BlockedStatus)
        assert RELATION_NAME in status.message

    def test_active_with_custom_required_relation_fields(self, harness, s3_component):
        """When custom required_relation_fields are satisfied, status should be Active."""
        harness.add_relation(RELATION_NAME, "remote-app")
        s3_component.required_relation_fields = frozenset({"bucket"})
        s3_component.s3_client.get_storage_connection_info.return_value = {"bucket": "my-bucket"}
        status = s3_component.get_status()
        assert isinstance(status, ActiveStatus)

    def test_blocked_when_optional_relation_present_but_no_data(
        self, harness, s3_component_optional
    ):
        """When the optional relation is present but returns no data, status should be Blocked."""
        harness.add_relation(RELATION_NAME, "remote-app")
        s3_component_optional.s3_client.get_storage_connection_info.return_value = None
        status = s3_component_optional.get_status()
        assert isinstance(status, BlockedStatus)
        assert RELATION_NAME in status.message


class TestS3RequirerComponentGetData:
    def test_get_data_returns_empty_list_when_no_relation(self, s3_component):
        """get_data() should return an empty list when no relation is present."""
        assert s3_component.get_data() == []

    def test_get_data_returns_connection_info(self, harness, s3_component):
        """get_data() should return a list with connection info for each related application."""
        harness.add_relation(RELATION_NAME, "remote-app")
        expected = {"endpoint": "https://s3.example.com", "bucket": "my-bucket"}
        s3_component.s3_client.get_storage_connection_info.return_value = expected
        assert s3_component.get_data() == [expected]

    def test_get_data_excludes_relations_without_data(self, harness, s3_component):
        """get_data() should exclude relations for which no data has been published."""
        harness.add_relation(RELATION_NAME, "remote-app")
        s3_component.s3_client.get_storage_connection_info.return_value = None
        assert s3_component.get_data() == []

    def test_get_data_includes_relations_with_incomplete_data(self, harness, s3_component):
        """get_data() should include relations even if only partial data has been published."""
        harness.add_relation(RELATION_NAME, "remote-app")
        partial = {"access-key": "key"}
        s3_component.s3_client.get_storage_connection_info.return_value = partial
        assert s3_component.get_data() == [partial]

    def test_get_data_returns_data_for_all_related_applications(self, harness, s3_component):
        """get_data() should return one entry per related application that has published data."""
        harness.add_relation(RELATION_NAME, "remote-app-1")
        harness.add_relation(RELATION_NAME, "remote-app-2")
        expected = {"access-key": "key", "secret-key": "secret", "bucket": "my-bucket"}
        s3_component.s3_client.get_storage_connection_info.return_value = expected
        assert s3_component.get_data() == [expected, expected]
