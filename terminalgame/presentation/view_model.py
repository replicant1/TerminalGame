"""Game logic. Owns the state, knows nothing about curses.

The screen never asks the ViewModel for anything -- it subscribes once and is
pushed a complete ViewState whenever something changes.
"""

from ..util.flow import StateFlow
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

# One cell of wall and one of open floor, each CELL_ROWS strings of CELL_COLS
# characters. Block glyphs rather than box-drawing: a border one cell thick has
# no corners to draw, and a solid block reads as a wall at this size.
_WALL_CELL = ("██",) * CELL_ROWS
_FLOOR_CELL = ("··",) * CELL_ROWS

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


def _build_maze() -> tuple:
    """A placeholder bordered arena, one cell thick, built cell by cell.

    Returns character rows, because that is what GameScreen draws. The cell
    structure exists only while this runs.
    """
    rows = []
    for cell_row in range(GRID_ROWS):
        lines = [""] * CELL_ROWS
        for cell_col in range(GRID_COLS):
            edge = (
                cell_row in (0, GRID_ROWS - 1)
                or cell_col in (0, GRID_COLS - 1)
            )
            cell = _WALL_CELL if edge else _FLOOR_CELL
            for i in range(CELL_ROWS):
                lines[i] += cell[i]
        rows.extend(lines)
    return tuple(rows)


class GameViewModel:
    """Turns ticks and key presses into ViewStates."""

    def __init__(self) -> None:
        self._maze = _build_maze()
        self._tick_count = 0
        # Positions are in game cells, not characters.
        self._player_row = GRID_ROWS // 2
        self._player_col = GRID_COLS // 2
        self._ghost_row = GRID_ROWS // 2 - 2
        self._ghost_col = 1
        self._ghost_direction = 1
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
        two of them.
        """
        self._player_row = self._clamp(self._player_row + d_row, 1, GRID_ROWS - 2)
        self._player_col = self._clamp(self._player_col + d_col, 1, GRID_COLS - 2)
        self._publish()

    # -- internals -------------------------------------------------------

    def _advance_ghost(self) -> None:
        next_col = self._ghost_col + self._ghost_direction
        if next_col <= 1 or next_col >= GRID_COLS - 2:
            self._ghost_direction *= -1
        self._ghost_col = self._clamp(next_col, 1, GRID_COLS - 2)

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
            background=self._maze,
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

    @staticmethod
    def _clamp(value: int, low: int, high: int) -> int:
        return max(low, min(high, value))
