"""Presentation logic: turns game events into the state the UI renders.

Holds no curses import and no terminal knowledge. It publishes ViewStates and
never learns who is collecting them.

`state` defines the vocabulary those ViewStates are written in, so it is
re-exported here: the UI depends on this package, not on the module layout
inside it.
"""

from .state import (
    COLOR_DEFAULT,
    COLOR_GHOST,
    COLOR_PLAYER,
    COLOR_STATUS,
    COLOR_WALL,
    PLAYFIELD_COLS,
    PLAYFIELD_ROWS,
    Sprite,
    ViewState,
)
from .view_model import GameViewModel

__all__ = [
    "GameViewModel",
    "Sprite",
    "ViewState",
    "PLAYFIELD_ROWS",
    "PLAYFIELD_COLS",
    "COLOR_DEFAULT",
    "COLOR_WALL",
    "COLOR_PLAYER",
    "COLOR_GHOST",
    "COLOR_STATUS",
]
