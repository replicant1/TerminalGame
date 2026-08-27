"""Immutable view state -- everything GameScreen needs to draw one frame.

Frozen dataclasses give us value equality for free, which is what lets
StateFlow skip redundant emissions, and guarantees the ViewModel can never
mutate a frame the screen is still holding.
"""

from dataclasses import dataclass, replace
from typing import Tuple

# The fixed playfield, in terminal character positions. The terminal window is
# resized to match at startup.
PLAYFIELD_ROWS = 30
PLAYFIELD_COLS = 40

# One game cell is a block of characters. The game's logic is expressed in
# cells; only GameScreen and the sprite art deal in characters.
#
# A terminal's own character cell is about twice as tall as it is wide -- 11.9
# by 24.6 points at the size the launcher asks for -- so a 2x2 block is a tall
# rectangle rather than a square. Two columns by one row would be square.
CELL_ROWS = 2
CELL_COLS = 2

# The playfield measured in game cells. The last character row is the status
# line, so it is taken off before dividing.
GRID_ROWS = (PLAYFIELD_ROWS - 1) // CELL_ROWS
GRID_COLS = PLAYFIELD_COLS // CELL_COLS

# Logical colour slots. GameScreen maps these onto curses colour pairs so the
# ViewModel never has to import curses.
COLOR_DEFAULT = 0
COLOR_WALL = 1
COLOR_PLAYER = 2
COLOR_GHOST = 3
COLOR_STATUS = 4


@dataclass(frozen=True)
class Sprite:
    """A block of glyphs drawn on top of the background.

    `art` is one string per character row, so a CELL_ROWS x CELL_COLS sprite is
    a tuple of CELL_ROWS strings of CELL_COLS characters. `row` and `col` are
    the character position of its top-left corner, not its cell -- the
    conversion happens in the ViewModel, so GameScreen never has to know that
    cells exist.
    """

    row: int
    col: int
    art: Tuple[str, ...]
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
