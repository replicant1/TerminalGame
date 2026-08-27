"""Composition root: the entry point and the window it launches itself into.

`main` owns argument parsing and the game loop; `launcher` opens the Terminal.app
window that loop runs in. This is the only package that knows how the pieces are
wired together, so it is the only one that imports from every other package.

`main` is deliberately not imported here -- it imports the parent package, and
pulling it in at package-import time would make that a cycle. Run it with
`python3 -m terminalgame.app.main`.
"""

from . import launcher

__all__ = ["launcher"]
