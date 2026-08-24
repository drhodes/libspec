# libspec/__init__.py
import pkgutil

__path__ = pkgutil.extend_path(
    __path__, __name__
)  # allow sibling distributions to extend the libspec.* namespace

from .common import *  # noqa: F403, F401
from .spec import *  # noqa: F403, F401
from .spec_types import *  # noqa: F403, F401
from .specweb import *  # noqa: F403, F401
from .user_story import *  # noqa: F403, F401
# from .spec_diff import *
