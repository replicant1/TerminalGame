"""Immutable view state -- everything GameScreen needs to draw one frame.

Frozen dataclasses give us value equality for free, which is what lets
StateFlow skip redundant emissions, and guarantees the ViewModel can never
mutate a frame the screen is still holding.
"""

from dataclasses import dataclass, replace
from typing import Tuple

# The fixed playfield. The terminal window is resized to match at startup.
PLAYFIELD_ROWS = 30
PLAYFIELD_COLS = 80

# Logical colour slots. GameScreen maps these onto curses colour pairs so the
# ViewModel never has to import curses.
COLOR_DEFAULT = 0
COLOR_WALL = 1
COLOR_PLAYER = 2
COLOR_GHOST = 3
COLOR_STATUS = 4


@dataclass(frozen=True)
class Sprite:
    """A single moving glyph drawn on top of the background."""

    row: int
    col: int
    glyph: str
    color: int = COLOR_DEFAULT


@dataclass(frozen=True)
class ViewState:
    """One complete frame.

    `background` is the static maze; `sprites` are the things that move. They
    are separated only for clarity -- GameScreen redraws both every frame and
    lets ncurses work out what actually changed.
    """

    background: Tuple[str, ...]
    sprites: Tuple[Sprite, ...]
    status_line: str
    tick: int = 0

    def with_sprites(self, *sprites: Sprite) -> "ViewState":
        return replace(self, sprites=tuple(sprites))
