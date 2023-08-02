# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities for testing SerializedDataInterface-backed relations."""
import dataclasses
from typing import Optional

import yaml
from ops.testing import Harness


@dataclasses.dataclass
class RelationMetadata:
    """Class representing the relation metadata returned by some helpers."""

    other_app: str
    other_unit: str
    rel_id: int
    data: dict


def add_data_to_sdi_relation(
    harness: Harness,
    rel_id: int,
    app_name: str,
    data: Optional[dict] = None,
    supported_versions: str = "- v1",
) -> None:
    """Add data to an SDI-backed relation.

    Args:
        harness: the test harness in use
        rel_id: the relation id of the relation to add data to
        app_name: the name of the app who is adding data to the relation, typically the other app
        data: dict of the data to add
        supported_versions: yaml formatted string of SDI supported versions to add to the relation
    """
    if data is None:
        data = {}

    harness.update_relation_data(
        rel_id,
        app_name,
        {"_supported_versions": supported_versions, "data": yaml.dump(data)},
    )


def add_sdi_relation_to_harness(
    harness: Harness, relation_name: str, other_app: str = "other", data: Optional[dict] = None
) -> RelationMetadata:
    """Relates a new app and unit to an sdi-formatted relation.

    Args:
        harness: the Harness to add a relation to
        relation_name: the name of the relation
        other_app: the name of the other app that is relating to our charm
        data: (optional) the data added to this relation

    Returns SdiRelationMetadata with:
    * other (str): The name of the other app
    * other_unit (str): The name of the other unit
    * rel_id (int): The relation id
    * data (dict): The relation data put to the relation
    """
    if data is None:
        data = {}

    other_unit = f"{other_app}/0"
    rel_id = harness.add_relation(relation_name, other_app)

    harness.add_relation_unit(rel_id, other_unit)

    add_data_to_sdi_relation(harness, rel_id, other_app, data)

    return RelationMetadata(
        other_app=other_app,
        other_unit=other_unit,
        rel_id=rel_id,
        data=data,
    )
