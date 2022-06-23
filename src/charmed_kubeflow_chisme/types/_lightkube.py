# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

from typing import List, Union

from lightkube.core.resource import GlobalResource, NamespacedResource

LightkubeResourceType = Union[NamespacedResource, GlobalResource]
LightkubeResourcesList = List[LightkubeResourceType]
