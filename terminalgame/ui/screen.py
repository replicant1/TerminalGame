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
    COLOR_PILL,
    COLOR_GHOST,
    COLOR_PLAYER,
    COLOR_STATUS,
    COLOR_WALL,
    PLAYFIELD_COLS,
    PLAYFIELD_ROWS,
    ViewState,
)

# Shades from the 256 colour cube. 226 is full yellow, 178 a darker gold, so
# the player reads as lit and the pills as something lying on the floor.
#
# 213 is a bright pink for the ghost. Measured against a black background it
# comes out at 8.3 to 1, where the terminal's own ANSI red manages 3.8 -- the
# dimmest thing on the screen apart from the walls, which are meant to recede.
# Pink rather than a brighter red because its hue is nowhere near the yellow
# of the player or the gold of the pills, so the ghost is told apart at a
# glance rather than by shade.
_BRIGHT_YELLOW = 226
_GOLD = 178
_BRIGHT_PINK = 213

# Terminals honouring the xterm window-manipulation sequence resize on this.
_RESIZE_SEQUENCE = "\033[8;{rows};{cols}t"
# Terminal.app resizes asynchronously; give it a moment before curses measures.
_RESIZE_SETTLE_SECONDS = 0.15


class TerminalTooSmall(RuntimeError):
    """Raised when the terminal could not be sized to the playfield."""


class GameScreen:
    """Owns the curses lifetime and paints ViewStates onto the terminal."""

    def __init__(self, rows: int = PLAYFIELD_ROWS, cols: int = PLAYFIELD_COLS) -> None:
        """Prepares a screen. Nothing touches curses until `open`.

        Args:
            rows: How many character rows the playfield needs.
            cols: How many character columns it needs.
        """
        self._rows = rows
        self._cols = cols
        self._stdscr = None
        self._unsubscribe = None
        self._color_pairs = {}

    # -- lifecycle -------------------------------------------------------

    def __enter__(self) -> "GameScreen":
        """Opens curses and returns the screen, for use as a context manager."""
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        """Restores the terminal, whether the block ended well or badly.

        Args:
            exc_type: Type of the exception leaving the block, if any.
            exc: The exception itself, if any.
            tb: Its traceback, if any.

        Returns:
            False, so an exception carries on rather than being swallowed by
            the terminal being tidied up.
        """
        self.close()
        return False

    def open(self) -> None:
        """Takes over the terminal: raw keys, no echo, no caret, colours.

        The terminal is asked to resize itself to the playfield first, since a
        window smaller than the playfield cannot be drawn into.

        Anything that goes wrong after `initscr` hands the terminal back before
        it propagates, because by then nothing else will: an exception here
        means `__enter__` never returns, so `__exit__` never runs and the
        `with` block that would have closed the screen was never entered.

        Raises:
            TerminalTooSmall: If the terminal ignored the resize request and
                is still shorter or narrower than the playfield.
            curses.error: If the terminal cannot do something curses needs.
                `curs_set` raises on a terminal whose terminfo has no cursor
                visibility, which vt100 and dumb do not.
        """
        locale.setlocale(locale.LC_ALL, "")  # required before any wide glyphs
        self._request_window_size()

        self._stdscr = curses.initscr()
        # Implement a "rollback on failed initialisation" strategy. initscr()
        # has acquired the terminal; everything below only configures or measures it,
        # and any of it can fail.
        #
        # What is being rolled back is the terminal's own settings -- its echo
        # and line-discipline flags, which initscr() changed -- and not any
        # state of this process's. That distinction is the point: the terminal
        # belongs to the user and outlives us, so exiting the process alone does
        # not undo the effects of the initscr() call.
        try:
            curses.noecho()          # don't echo typed keys onto the playfield
            curses.cbreak()          # deliver keys immediately, no Enter needed
            curses.curs_set(0)       # hide the caret so it can't flash across a frame
            self._stdscr.keypad(True)  # decode arrow keys into KEY_* constants
            self._init_colors()

            height, width = self._stdscr.getmaxyx()
            if height < self._rows or width < self._cols:
                raise TerminalTooSmall(
                    "Need at least {}x{} (rows x cols); terminal is {}x{}. "
                    "Your terminal ignored the resize request -- resize it by hand.".format(
                        self._rows, self._cols, height, width
                    )
                )
        except BaseException:
            # endwin(), inside close(), is the call that does the restoring: it
            # puts back the tty state ncurses saved during initscr(). The rest
            # of close() is tidying -- echo() alone does not bring echo back.
            self.close()
            raise

    def close(self) -> None:
        """Gives the terminal back, and stops collecting the state flow.

        Safe to call twice: a screen that was never opened, or has been closed
        already, does nothing.

        Safe on a terminal that refuses the tidying up, too. Restoring the
        caret raises where hiding it did, and the terminals that cannot do
        either are exactly the ones this has to work on, since they are why
        `open` failed. `endwin` is the call that actually hands the terminal
        back, so it runs whatever the cosmetic ones did.
        """
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._stdscr is not None:
            try:
                try:
                    curses.curs_set(1)
                except curses.error:
                    pass  # no cursor visibility here, so none was hidden either
                self._stdscr.keypad(False)
                curses.nocbreak()
                curses.echo()
            finally:
                curses.endwin()
                self._stdscr = None

    def _request_window_size(self) -> None:
        """Asks the terminal to resize itself, then waits for it to land."""
        sys.stdout.write(_RESIZE_SEQUENCE.format(rows=self._rows, cols=self._cols))
        sys.stdout.flush()
        time.sleep(_RESIZE_SETTLE_SECONDS)

    def _init_colors(self) -> None:
        """Maps the logical colour slots onto curses colour pairs.

        Does nothing on a terminal without colour, where every slot then draws
        in the default attribute.
        """
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()  # keep the terminal's own background
            background = -1
        except curses.error:
            background = curses.COLOR_BLACK

        # The player and the pills are both yellow, and the player has to be
        # the brighter of the two or it disappears into the pills it is eating.
        # Where 256 colours are available the two shades are named outright,
        # which is exact. Otherwise the player falls back to bold yellow, which
        # most terminals render brighter -- though that depends on a setting
        # the terminal owns, which is why it is the fallback and not the rule.
        if curses.COLORS >= 256:
            player, player_attribute = _BRIGHT_YELLOW, curses.A_NORMAL
            pill = _GOLD
            ghost, ghost_attribute = _BRIGHT_PINK, curses.A_NORMAL
        else:
            player, player_attribute = curses.COLOR_YELLOW, curses.A_BOLD
            pill = curses.COLOR_YELLOW
            ghost, ghost_attribute = curses.COLOR_RED, curses.A_BOLD

        palette = {
            COLOR_WALL: (curses.COLOR_BLUE, curses.A_NORMAL),
            COLOR_PLAYER: (player, player_attribute),
            COLOR_GHOST: (ghost, ghost_attribute),
            COLOR_STATUS: (curses.COLOR_CYAN, curses.A_NORMAL),
            COLOR_PILL: (pill, curses.A_NORMAL),
        }
        for slot, (foreground, attribute) in palette.items():
            curses.init_pair(slot, foreground, background)
            self._color_pairs[slot] = curses.color_pair(slot) | attribute

    # -- wiring ----------------------------------------------------------

    def attach(self, view_model) -> None:
        """Collects the ViewModel's state flow, painting the current frame at once.

        Args:
            view_model: The ViewModel whose `state` flow to subscribe to. The
                screen only ever receives frames; it never asks for one.

        Raises:
            RuntimeError: If the screen has not been opened yet.
        """
        if self._stdscr is None:
            raise RuntimeError("GameScreen.open() must be called before attach()")
        self._unsubscribe = view_model.state.subscribe(self.render)

    # -- input -----------------------------------------------------------

    def set_input_timeout(self, milliseconds: int) -> None:
        """Bounds how long `read_key` blocks, so the loop can poll the clock.

        Args:
            milliseconds: How long to wait for a key before giving up. This is
                input latency, not the frame rate.
        """
        self._stdscr.timeout(milliseconds)

    def read_key(self):
        """Reads one key press, waiting no longer than the input timeout.

        Returns:
            A curses key code, or None if the timeout elapsed with no input.
        """
        key = self._stdscr.getch()
        return None if key == -1 else key

    def handle_resize(self) -> None:
        """Re-measures the terminal after KEY_RESIZE and repaints from scratch."""
        curses.update_lines_cols()
        self._stdscr.clearok(True)

    # -- rendering -------------------------------------------------------

    def render(self, state: ViewState) -> None:
        """Draws one complete frame. This is the StateFlow collector.

        Args:
            state: The frame to draw. Every layer is drawn in full and ncurses
                works out which character positions actually changed.
        """
        if self._stdscr is None:
            return
        window = self._stdscr
        height, width = window.getmaxyx()

        window.erase()

        # One pass per layer, each in its own colour. Only the non-blank runs
        # of a layer are drawn: a space is a character like any other, so
        # writing a layer whole would paint its gaps over the layer beneath.
        # erase() has already blanked the window, so the gaps need no drawing.
        for rows, color in ((state.walls, COLOR_WALL), (state.pills, COLOR_PILL)):
            for row_index, row_text in enumerate(rows):
                if row_index >= min(self._rows, height):
                    break
                self._put_runs(window, row_index, row_text, color, height, width)

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

    def _put_runs(self, window, row, text, color_slot, height, width):
        """Draws each run of non-space characters in a layer, skipping the gaps.

        A space is a character like any other, so writing a layer whole would
        paint its gaps over the layer beneath.

        Args:
            window: The curses window to draw into.
            row: Character row to draw on.
            text: The layer's text for that row.
            color_slot: Logical colour to draw the runs in.
            height: Height of the window, for bounds checking.
            width: Width of the window, for bounds checking.
        """
        col, end_of_text = 0, len(text)
        while col < end_of_text:
            if text[col] == " ":
                col += 1
                continue
            run_end = col
            while run_end < end_of_text and text[run_end] != " ":
                run_end += 1
            self._put(
                window, row, col, text[col:run_end], color_slot, height, width
            )
            col = run_end

    def _put(self, window, row, col, text, color_slot, height, width):
        """Writes text at one position, clipping rather than raising.

        Writing the bottom-right cell of a window raises in curses, and a
        sprite hanging off an edge would too, so both are clipped here instead
        of being guarded at every call site.

        Args:
            window: The curses window to draw into.
            row: Character row to write at.
            col: Character column to start at.
            text: The characters to write.
            color_slot: Logical colour to write them in.
            height: Height of the window, for bounds checking.
            width: Width of the window, for bounds checking.
        """
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
