# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import List, Optional, Set, Type, Union

from lightkube.core.resource import GlobalResource, NamespacedResource

LightkubeResourceType = Union[NamespacedResource, GlobalResource]
LightkubeResourcesList = List[LightkubeResourceType]

# A Set of the classes of valid Lightkube Resources, not instances of those classes
LightkubeResourceTypesSet = Optional[Set[Type[LightkubeResourceType]]]
