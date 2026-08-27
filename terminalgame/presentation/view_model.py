"""Game logic. Owns the state, knows nothing about curses.

The screen never asks the ViewModel for anything -- it subscribes once and is
pushed a complete ViewState whenever something changes.
"""

import random
from typing import Optional, Tuple

from ..util.flow import StateFlow
from .maze import Maze
from .state import (
    CELL_COLS,
    CELL_ROWS,
    COLOR_GHOST,
    COLOR_PLAYER,
    GRID_COLS,
    GRID_ROWS,
    Sprite,
    ViewState,
)

# One cell of wall and one of open corridor, each CELL_ROWS strings of
# CELL_COLS characters. Block glyphs rather than box-drawing: walls here are
# solid regions rather than outlines, so there are no corners to draw.
#
# A corridor carries exactly one dot, because a sprite occupies one cell and a
# dot marks one place a sprite can stand. Two dots in a cell would say there
# were two such places.
#
# The dot is a pair of quadrant blocks: lower-right, then lower-left. Each
# fills the quarter of its own character nearest the other, so back to back
# they meet and read as one small solid block with a gap either side -- a
# single pellet, rather than a mark at one edge of the cell.
#
# Quadrants rather than half blocks because a half block pair fills the cell's
# full height, which at this size reads as a bar rather than a pellet. The
# quadrant pair is half as tall and very nearly square.
_WALL_CELL = ("██",) * CELL_ROWS
_PILL_CELL = ("▗▖",) * CELL_ROWS
# What a layer holds where the other layer has something. GameScreen skips
# these rather than drawing them: a space is a character like any other, and
# writing one would paint over whatever the earlier pass put there.
_BLANK_CELL = (" " * CELL_COLS,) * CELL_ROWS

# Sprites are one cell each. Quadrant glyphs, which every monospaced font that
# has box-drawing also has, chosen so the two read differently in shape as well
# as in colour: the player is weighted to the top, the ghost to the bottom.
_PLAYER_ART = ("▛▜",)
_GHOST_ART = ("▙▟",)

# A sprite whose art does not match the cell would draw over its neighbours or
# leave part of the cell showing through. Cheap to check once, at import.
for _name, _art in (("player", _PLAYER_ART), ("ghost", _GHOST_ART)):
    if len(_art) != CELL_ROWS or any(len(line) != CELL_COLS for line in _art):
        raise ValueError(
            "{} art is {}x{}, but a cell is {}x{}".format(
                _name, len(_art), len(_art[0]), CELL_ROWS, CELL_COLS
            )
        )

def _to_layers(maze) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Turn a Maze into the two character layers GameScreen draws.

    Returns the walls and the pills separately, each blank where the other has
    something, because a layer is drawn in a single colour.

    Every open cell gets its one pill. Wall cells get none, so the solid
    islands braiding leaves behind come out blank inside without anything
    having to go looking for them: a cell that was never carved is simply
    never given a pill.
    """
    walls, pills = [], []
    for cell_row in range(maze.rows):
        wall_lines = [""] * CELL_ROWS
        pill_lines = [""] * CELL_ROWS
        for cell_col in range(maze.cols):
            open_cell = maze.is_open(cell_row, cell_col)
            wall = _BLANK_CELL if open_cell else _WALL_CELL
            pill = _PILL_CELL if open_cell else _BLANK_CELL
            for i in range(CELL_ROWS):
                wall_lines[i] += wall[i]
                pill_lines[i] += pill[i]
        walls.extend(wall_lines)
        pills.extend(pill_lines)
    return tuple(walls), tuple(pills)


class GameViewModel:
    """Turns ticks and key presses into ViewStates."""

    def __init__(self, seed: Optional[int] = None) -> None:
        # A seed makes a maze reproducible, which is what lets a test assert
        # anything about one. Left out, every run gets a different maze.
        self._maze = Maze.generate(GRID_ROWS, GRID_COLS, seed=seed)
        self._walls, self._pills = _to_layers(self._maze)
        self._rng = random.Random(seed)
        self._tick_count = 0
        # Positions are in game cells, not characters. Both have to start on
        # open corridor, which no fixed coordinate can promise once the maze
        # is random.
        self._player_row, self._player_col = self._maze.nearest_open(
            GRID_ROWS // 2, GRID_COLS // 2
        )
        self._ghost_row, self._ghost_col = self._maze.farthest_open(
            self._player_row, self._player_col
        )
        self._ghost_step = (0, 1)
        self._state: StateFlow[ViewState] = StateFlow(self._build_state())

    @property
    def state(self) -> StateFlow[ViewState]:
        """The flow GameScreen collects from."""
        return self._state

    # -- inputs ----------------------------------------------------------

    def tick(self) -> None:
        """Called by GameClock. Advance the simulation by one step."""
        self._tick_count += 1
        self._advance_ghost()
        self._publish()

    def on_direction(self, d_row: int, d_col: int) -> None:
        """Called by GameScreen when the player presses an arrow key.

        One press moves one whole cell, so the player never lands straddling
        two of them. A press into a wall does nothing, which leaves the frame
        identical and costs the terminal nothing.
        """
        row, col = self._player_row + d_row, self._player_col + d_col
        if self._maze.is_open(row, col):
            self._player_row, self._player_col = row, col
            self._publish()

    # -- internals -------------------------------------------------------

    def _advance_ghost(self) -> None:
        """Carry straight on where possible, otherwise turn.

        Because the maze has no dead ends, a ghost that has just arrived
        somewhere always has a way on that is not the way it came. Reversing
        is a last resort rather than the usual outcome.
        """
        d_row, d_col = self._ghost_step
        ahead = (self._ghost_row + d_row, self._ghost_col + d_col)
        if self._maze.is_open(*ahead):
            self._ghost_row, self._ghost_col = ahead
            return
        back = (-d_row, -d_col)
        turns = [
            step
            for step in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if step != back
            and self._maze.is_open(self._ghost_row + step[0], self._ghost_col + step[1])
        ]
        if not turns:
            turns = [back]
        self._ghost_step = self._rng.choice(turns)
        self._ghost_row += self._ghost_step[0]
        self._ghost_col += self._ghost_step[1]

    def _publish(self) -> None:
        # StateFlow drops this silently if nothing actually changed.
        self._state.emit(self._build_state())

    def _build_state(self) -> ViewState:
        # The last row loses its final cell to curses, so the budget is
        # PLAYFIELD_COLS - 1, which is 39. Row and column are two digits at
        # most, so the tick count is the only part that can grow: six digits
        # give 38 characters and seven give 39. Beyond 9,999,999 ticks, which
        # is about seventeen days of play, _put clips the trailing space.
        status = " tick {:<6} at {:>2},{:<2} arrows, q quits ".format(
            self._tick_count, self._player_row, self._player_col
        )
        return ViewState(
            walls=self._walls,
            pills=self._pills,
            sprites=(
                # Cell coordinates become character coordinates here, and
                # nowhere else.
                Sprite(
                    self._ghost_row * CELL_ROWS, self._ghost_col * CELL_COLS,
                    _GHOST_ART, COLOR_GHOST,
                ),
                Sprite(
                    self._player_row * CELL_ROWS, self._player_col * CELL_COLS,
                    _PLAYER_ART, COLOR_PLAYER,
                ),
            ),
            status_line=status,
            tick=self._tick_count,
        )
