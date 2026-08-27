"""Game logic. Owns the state, knows nothing about curses.

The screen never asks the ViewModel for anything -- it subscribes once and is
pushed a complete ViewState whenever something changes.
"""

from ..util.flow import StateFlow
from .state import (
    COLOR_GHOST,
    COLOR_PLAYER,
    PLAYFIELD_COLS,
    PLAYFIELD_ROWS,
    Sprite,
    ViewState,
)

# The maze occupies every row except the last, which is the status line.
MAZE_ROWS = PLAYFIELD_ROWS - 1


def _build_maze() -> tuple:
    """A placeholder bordered arena. Swap this for a real Pac-Man maze later."""
    inner_width = PLAYFIELD_COLS - 2
    top = "╔" + "═" * inner_width + "╗"
    bottom = "╚" + "═" * inner_width + "╝"
    middle = "║" + "·" * inner_width + "║"
    return (top,) + (middle,) * (MAZE_ROWS - 2) + (bottom,)


class GameViewModel:
    """Turns ticks and key presses into ViewStates."""

    def __init__(self) -> None:
        self._maze = _build_maze()
        self._tick_count = 0
        self._player_row = MAZE_ROWS // 2
        self._player_col = PLAYFIELD_COLS // 2
        self._ghost_row = MAZE_ROWS // 2 - 3
        self._ghost_col = 2
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
        """Called by GameScreen when the player presses an arrow key."""
        self._player_row = self._clamp(self._player_row + d_row, 1, MAZE_ROWS - 2)
        self._player_col = self._clamp(self._player_col + d_col, 1, PLAYFIELD_COLS - 2)
        self._publish()

    # -- internals -------------------------------------------------------

    def _advance_ghost(self) -> None:
        next_col = self._ghost_col + self._ghost_direction
        if next_col <= 1 or next_col >= PLAYFIELD_COLS - 2:
            self._ghost_direction *= -1
        self._ghost_col = self._clamp(next_col, 1, PLAYFIELD_COLS - 2)

    def _publish(self) -> None:
        # StateFlow drops this silently if nothing actually changed.
        self._state.emit(self._build_state())

    def _build_state(self) -> ViewState:
        status = " tick {:<5} player {:>2},{:<2}   arrows to move, q to quit ".format(
            self._tick_count, self._player_row, self._player_col
        )
        return ViewState(
            background=self._maze,
            sprites=(
                Sprite(self._ghost_row, self._ghost_col, "M", COLOR_GHOST),
                Sprite(self._player_row, self._player_col, "C", COLOR_PLAYER),
            ),
            status_line=status,
            tick=self._tick_count,
        )

    @staticmethod
    def _clamp(value: int, low: int, high: int) -> int:
        return max(low, min(high, value))
