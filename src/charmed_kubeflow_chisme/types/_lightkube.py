# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import List, Optional, Type, Union

from lightkube.core.resource import GlobalResource, NamespacedResource

LightkubeResourceType = Union[NamespacedResource, GlobalResource]
LightkubeResourcesList = List[LightkubeResourceType]

# A List of the classes of valid Lightkube Resources, not instances of those classes
LightkubeResourceTypesList = Optional[List[Type[LightkubeResourceType]]]
