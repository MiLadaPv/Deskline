"""Contract checks for public API fingerprints used by the desktop shell."""

from __future__ import annotations

import inspect

from deskline import __version__
from deskline.api import create_app


def test_health_route_advertises_local_python_edition() -> None:
    source = inspect.getsource(create_app)
    assert '"edition": "local-python"' in source or "'edition': 'local-python'" in source
    assert __version__
