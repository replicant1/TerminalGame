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
# cells: positions, movement and collisions are all counted in them. The
# conversion to character coordinates happens in one place only, where
# GameViewModel builds its sprites, so GameScreen is handed character
# positions and never learns that cells exist.
#
# A terminal's own character cell is about twice as tall as it is wide -- 11.9
# by 24.6 points at the size the launcher asks for -- so one row by two columns
# comes out very nearly square, at 23.9 by 24.6. That is why the cell is this
# shape and not 2x2, which would be a rectangle twice as tall as it is wide.
CELL_ROWS = 1
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
COLOR_PILL = 5


@dataclass(frozen=True)
class Sprite:
    """A block of glyphs drawn on top of the background.

    Attributes:
        row: Character row of the art's top-left corner, not its cell. The
            conversion from cells happens in the ViewModel, so GameScreen
            never has to know that cells exist.
        col: Character column of that same corner.
        art: One string per character row. Its width is odd rather than a
            cell's width: a sprite is drawn centred on the corridor's centre
            line, which is the left character of its cell, and only an odd
            width can sit centred on a character -- so a sprite wider than one
            character overhangs into the blank character either side of it.
        color: Which logical colour slot to draw the art in.
    """

    row: int
    col: int
    art: Tuple[str, ...]
    color: int = COLOR_DEFAULT


@dataclass(frozen=True)
class ViewState:
    """One complete frame.

    Every part of a frame is redrawn every time, and ncurses works out which
    character positions actually changed.

    Attributes:
        walls: The wall layer, one string per character row, blank wherever
            the pill layer has something. The maze arrives as two layers
            rather than one because a layer is drawn in a single colour, and
            splitting them is what lets the pills be a different colour from
            the walls they sit between.
        pills: The pellet layer, blank wherever the wall layer has something.
        sprites: The things that move, drawn over both layers in the order
            given.
        status_line: The row of readings underneath the playfield.
        tick: How many times the clock has fired, carried so a test can tell
            two otherwise identical frames apart.
    """

    walls: Tuple[str, ...]
    pills: Tuple[str, ...]
    sprites: Tuple[Sprite, ...]
    status_line: str
    tick: int = 0

    def _with_sprites(self, *sprites: Sprite) -> "ViewState":
        """Returns a copy of this frame carrying different sprites.

        Args:
            *sprites: The sprites the new frame should have, replacing rather
                than adding to the ones this frame holds.

        Returns:
            A new frame, since a ViewState is frozen and never edited in
            place.
        """
        return replace(self, sprites=tuple(sprites))
