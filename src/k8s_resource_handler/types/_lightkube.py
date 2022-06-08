from typing import List, Union

from lightkube.core.resource import NamespacedResource, GlobalResource


LightkubeResourceType = Union[NamespacedResource, GlobalResource]
LightkubeResourcesList = List[LightkubeResourceType]
