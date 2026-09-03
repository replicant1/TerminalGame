"""Stand-ins for the two things a test cannot have: a terminal and curses.

Both are fakes rather than stubs -- they behave the way the real ones do where
the behaviour is what is being tested. FakeWindow refuses a write that lands
off the window, exactly as curses does, so a test can tell a guard that clips
from a guard that is not there at all.
"""

import curses


class FakeWindow:
    """A curses window that records what was drawn on it."""

    def __init__(self, height=30, width=40):
        self.height = height
        self.width = width
        self.writes = []       # (row, col, text, attribute), clipped as curses would
        self.erases = 0
        self.refreshes = 0
        self.cleared_ok = []
        self.timeouts = []
        self.keypads = []
        self.cursor = None
        self.keys = []         # scripted key codes for getch()

    # -- what GameScreen draws with --------------------------------------

    def getmaxyx(self):
        return (self.height, self.width)

    def erase(self):
        self.erases += 1

    def addnstr(self, row, col, text, limit, attribute):
        if not text:
            return  # curses writes nothing and reports success
        if not (0 <= row < self.height) or not (0 <= col < self.width):
            raise curses.error("addnstr() returned ERR")
        if row == self.height - 1 and col + min(len(text), limit) >= self.width:
            raise curses.error("addnstr() returned ERR")  # scrolls the window
        self.writes.append((row, col, text[:limit], attribute))

    def move(self, row, col):
        if not (0 <= row < self.height) or not (0 <= col < self.width):
            raise curses.error("move() returned ERR")
        self.cursor = (row, col)

    def noutrefresh(self):
        self.refreshes += 1

    # -- what GameScreen reads and configures ----------------------------

    def keypad(self, enabled):
        self.keypads.append(enabled)

    def clearok(self, enabled):
        self.cleared_ok.append(enabled)

    def timeout(self, milliseconds):
        self.timeouts.append(milliseconds)

    def getch(self):
        """Returns the next scripted key, or -1 once they run out.

        -1 is what curses returns on a timeout, so a test that forgets to
        script a quit key ends the loop rather than hanging in it.
        """
        return self.keys.pop(0) if self.keys else -1

    # -- for assertions ---------------------------------------------------

    def text_at(self, row, col):
        """Returns what was last written at a position, or None."""
        for write_row, write_col, text, _ in reversed(self.writes):
            if write_row == row and write_col == col:
                return text
        return None

    def drawn_rows(self):
        return {write[0] for write in self.writes}


class FakeCurses:
    """The curses module, minus the terminal.

    Only what GameScreen's lifecycle touches. Colour pairs are real
    bookkeeping rather than recorded calls, so a test can ask what colour a
    slot actually ended up with.
    """

    error = curses.error
    A_NORMAL = curses.A_NORMAL
    A_BOLD = curses.A_BOLD
    A_DIM = curses.A_DIM
    COLOR_BLACK = curses.COLOR_BLACK
    COLOR_BLUE = curses.COLOR_BLUE
    COLOR_CYAN = curses.COLOR_CYAN
    COLOR_RED = curses.COLOR_RED
    COLOR_YELLOW = curses.COLOR_YELLOW

    def __init__(self, window=None, colors=256, supports_default_colors=True,
                 supports_cursor_visibility=True):
        self.window = window if window is not None else FakeWindow()
        self.COLORS = colors
        self.supports_default_colors = supports_default_colors
        # vt100 and dumb have no civis/cnorm, and curs_set raises on both --
        # in either direction, so hiding the caret and restoring it both fail.
        self.supports_cursor_visibility = supports_cursor_visibility
        self.pairs = {}        # slot -> (foreground, background)
        self.calls = []
        self.updates = 0

    def initscr(self):
        self.calls.append("initscr")
        return self.window

    def noecho(self):
        self.calls.append("noecho")

    def cbreak(self):
        self.calls.append("cbreak")

    def nocbreak(self):
        self.calls.append("nocbreak")

    def echo(self):
        self.calls.append("echo")

    def endwin(self):
        self.calls.append("endwin")

    def curs_set(self, visibility):
        if not self.supports_cursor_visibility:
            raise curses.error("curs_set() returned ERR")
        self.calls.append("curs_set {}".format(visibility))

    def has_colors(self):
        return self.COLORS > 0

    def start_color(self):
        self.calls.append("start_color")

    def use_default_colors(self):
        if not self.supports_default_colors:
            raise curses.error("terminal has no default colours")
        self.calls.append("use_default_colors")

    def init_pair(self, slot, foreground, background):
        self.pairs[slot] = (foreground, background)

    def color_pair(self, slot):
        return slot << 8

    def doupdate(self):
        self.updates += 1

    def update_lines_cols(self):
        self.calls.append("update_lines_cols")


class LoopDidNotQuit(AssertionError):
    """Raised when the game loop read past the end of its scripted keys."""


class FakeScreen:
    """A GameScreen for the game loop to drive, with a scripted keyboard.

    Subscribes to the ViewModel the way the real screen does, so a test can
    see the frames the loop actually caused.

    Reading past the script fails the test rather than hanging it: a loop that
    ignores its quit key would otherwise sit there forever, and a suite that
    hangs is worse than one that goes red.
    """

    def __init__(self, keys=(), idle_reads=0):
        self.keys = list(keys)
        self.idle_reads = idle_reads
        self.frames = []
        self.timeout = None
        self.resizes = 0

    def attach(self, view_model):
        view_model.state.subscribe(self.render)

    def set_input_timeout(self, milliseconds):
        self.timeout = milliseconds

    def read_key(self):
        """Hands out the next scripted key, then None as a real timeout would."""
        if self.keys:
            return self.keys.pop(0)
        if self.idle_reads > 0:
            self.idle_reads -= 1
            return None
        raise LoopDidNotQuit("the loop read past its scripted keys without quitting")

    def handle_resize(self):
        self.resizes += 1

    def render(self, state):
        self.frames.append(state)
