"""The curses front end. Renders ViewState, reads the keyboard, owns nothing else.

Rendering strategy
------------------
Every frame is drawn in full into the curses back buffer, then handed to
`doupdate()`. ncurses diffs the back buffer against what is physically on the
terminal and emits escape codes only for the cells that changed, so publishing
whole ViewStates costs no more wire traffic than hand-rolled deltas would.

Three details keep it artifact-free:
  * `erase()` (not `clear()`) -- clear() forces a full repaint of the terminal
    on the next refresh, which is exactly the flicker we want to avoid.
  * `noutrefresh()` + `doupdate()` -- one atomic terminal write per frame
    instead of one per window.
  * `curs_set(0)` plus parking the cursor bottom-left -- no cursor tracking the
    draw position across the screen.
"""

import curses
import locale
import sys
import time

from ..presentation.state import (
    COLOR_DEFAULT,
    COLOR_GHOST,
    COLOR_PLAYER,
    COLOR_STATUS,
    COLOR_WALL,
    PLAYFIELD_COLS,
    PLAYFIELD_ROWS,
    ViewState,
)

# Terminals honouring the xterm window-manipulation sequence resize on this.
_RESIZE_SEQUENCE = "\033[8;{rows};{cols}t"
# Terminal.app resizes asynchronously; give it a moment before curses measures.
_RESIZE_SETTLE_SECONDS = 0.15


class TerminalTooSmall(RuntimeError):
    """Raised when the terminal could not be sized to the playfield."""


class GameScreen:
    """Owns the curses lifetime and paints ViewStates onto the terminal."""

    def __init__(self, rows: int = PLAYFIELD_ROWS, cols: int = PLAYFIELD_COLS) -> None:
        self._rows = rows
        self._cols = cols
        self._stdscr = None
        self._unsubscribe = None
        self._color_pairs = {}

    # -- lifecycle -------------------------------------------------------

    def __enter__(self) -> "GameScreen":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def open(self) -> None:
        locale.setlocale(locale.LC_ALL, "")  # required before any wide glyphs
        self._request_window_size()

        self._stdscr = curses.initscr()
        curses.noecho()          # don't echo typed keys onto the playfield
        curses.cbreak()          # deliver keys immediately, no Enter needed
        curses.curs_set(0)       # hide the caret so it can't flash across a frame
        self._stdscr.keypad(True)  # decode arrow keys into KEY_* constants
        self._init_colors()

        height, width = self._stdscr.getmaxyx()
        if height < self._rows or width < self._cols:
            self.close()
            raise TerminalTooSmall(
                "Need at least {}x{} (rows x cols); terminal is {}x{}. "
                "Your terminal ignored the resize request -- resize it by hand.".format(
                    self._rows, self._cols, height, width
                )
            )

    def close(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._stdscr is not None:
            curses.curs_set(1)
            self._stdscr.keypad(False)
            curses.nocbreak()
            curses.echo()
            curses.endwin()
            self._stdscr = None

    def _request_window_size(self) -> None:
        sys.stdout.write(_RESIZE_SEQUENCE.format(rows=self._rows, cols=self._cols))
        sys.stdout.flush()
        time.sleep(_RESIZE_SETTLE_SECONDS)

    def _init_colors(self) -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()  # keep the terminal's own background
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK

        palette = {
            COLOR_WALL: curses.COLOR_BLUE,
            COLOR_PLAYER: curses.COLOR_YELLOW,
            COLOR_GHOST: curses.COLOR_RED,
            COLOR_STATUS: curses.COLOR_CYAN,
        }
        for slot, foreground in palette.items():
            curses.init_pair(slot, foreground, background)
            self._color_pairs[slot] = curses.color_pair(slot)

    # -- wiring ----------------------------------------------------------

    def attach(self, view_model) -> None:
        """Collect the ViewModel's state flow. Renders the current frame at once."""
        if self._stdscr is None:
            raise RuntimeError("GameScreen.open() must be called before attach()")
        self._unsubscribe = view_model.state.subscribe(self.render)

    # -- input -----------------------------------------------------------

    def set_input_timeout(self, milliseconds: int) -> None:
        """Bound how long getch() blocks, so the main loop can also poll the clock."""
        self._stdscr.timeout(milliseconds)

    def read_key(self):
        """Return a key code, or None if the timeout elapsed with no input."""
        key = self._stdscr.getch()
        return None if key == -1 else key

    def handle_resize(self) -> None:
        """Re-measure after KEY_RESIZE and repaint from scratch."""
        curses.update_lines_cols()
        self._stdscr.clearok(True)

    # -- rendering -------------------------------------------------------

    def render(self, state: ViewState) -> None:
        """Draw one complete frame. This is the StateFlow collector."""
        if self._stdscr is None:
            return
        window = self._stdscr
        height, width = window.getmaxyx()

        window.erase()

        for row_index, row_text in enumerate(state.background):
            if row_index >= min(self._rows, height):
                break
            self._put(window, row_index, 0, row_text, COLOR_WALL, height, width)

        for sprite in state.sprites:
            # One _put per character row of the sprite. Bounds are checked
            # inside _put, so a sprite hanging off an edge simply loses the
            # rows and columns that fall outside.
            for offset, line in enumerate(sprite.art):
                self._put(
                    window, sprite.row + offset, sprite.col, line,
                    sprite.color, height, width,
                )

        status_row = min(self._rows, height) - 1
        self._put(window, status_row, 0, state.status_line, COLOR_STATUS, height, width)

        # Park the caret somewhere harmless in case the terminal shows it anyway.
        try:
            window.move(height - 1, 0)
        except curses.error:
            pass

        window.noutrefresh()
        curses.doupdate()  # single atomic write of only the changed cells

    def _put(self, window, row, col, text, color_slot, height, width):
        """Bounds-safe addnstr. Writing the bottom-right cell raises in curses."""
        if not (0 <= row < height) or col >= width:
            return
        limit = width - col
        if row == height - 1:
            limit -= 1  # never touch the final cell; it scrolls the window
        if limit <= 0:
            return
        attribute = self._color_pairs.get(color_slot, curses.A_NORMAL)
        if color_slot == COLOR_DEFAULT:
            attribute = curses.A_NORMAL
        try:
            window.addnstr(row, col, text, limit, attribute)
        except curses.error:
            pass
