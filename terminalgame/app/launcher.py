"""Spawns the game in its own correctly-sized Terminal.app window.

Terminal.app's scripting interface exposes writable `number of rows` and
`number of columns` on a tab, so the window is created at exactly 30x40 rather
than being opened at the default size and resized afterwards -- no visible
snap. `tty` on the same tab is what lets us find the window we just made and
close it again when the game exits.

The launcher process stays alive in the original terminal, waiting on a
sentinel file the game writes, so `python3 -m terminalgame.app.main` behaves
like a normal blocking command and forwards the game's exit code.
"""

import os
import shlex
import subprocess
import sys
import tempfile
import time
from typing import List, Optional, Tuple

# How long to wait for the child to announce itself before assuming it never
# started (bad interpreter path, Terminal refused the script, ...).
STARTUP_TIMEOUT_SECONDS = 20.0
# The child is re-run as a module, so the project root -- not this file's
# directory -- is what has to be on the shell's cwd for the import to resolve.
MAIN_MODULE = "terminalgame.app.main"

# Shown in the window's title bar, in place of the internal command line.
WINDOW_TITLE = "Terminal Game"

# Point size for the game window only, set on the tab rather than in a profile,
# so no other Terminal window is affected. Rows and columns are counted in
# characters, so a larger font grows the window in pixels and leaves the
# playfield at exactly PLAYFIELD_ROWS x PLAYFIELD_COLS. Raise it far enough and
# the window will not fit the display, Terminal will hand back fewer rows than
# were asked for, and GameScreen raises TerminalTooSmall.
FONT_SIZE = 18

# The game window's own background, independent of whatever profile the user's
# other Terminal windows use. Set on the tab, so nothing else is affected.
# AppleScript wants an RGB triple of 16-bit components, so black is three zeros.
BACKGROUND_COLOR = "{0, 0, 0}"

# How far below and to the right of the window that was in front the game's own
# window is placed.
#
# Terminal remembers where a window of a given profile was last put, and puts
# the next one back there. That is usually helpful and occasionally useless: a
# remembered position can be on a display that is no longer attached, or -- on a
# machine with several displays -- in the gap between two of them, where no
# screen covers the pixels and the window is invisible while being, as far as
# the window server is concerned, perfectly fine.
#
# Placing the game relative to a window the user demonstrably has in front of
# them avoids the whole question. It cannot land somewhere unseen, because it
# lands next to something being looked at.
WINDOW_OFFSET = 48

# Terminal appends the running process's arguments to the window title and that
# part is not scriptable per-tab, so the child is configured through the
# environment instead of argv -- the title then reads just the module name,
# with no sentinel path trailing it.
ENV_CHILD = "TERMINALGAME_CHILD"
ENV_SENTINEL = "TERMINALGAME_SENTINEL"
# Sentinel polling interval. This is a stat() on a local file, not an osascript
# call -- the game window is never polled over AppleScript.
POLL_INTERVAL_SECONDS = 0.1

_SPAWN_SCRIPT = '''
tell application "Terminal"
    -- Captured *before* the new tab exists, so there is no question of which
    -- window this is. Matching a window by its name or its tab's title after
    -- the fact is unreliable: Terminal puts the running command in the name,
    -- and a window running this very script can match a search for it.
    set anchorBounds to missing value
    try
        if (count of windows) > 0 then set anchorBounds to bounds of front window
    end try

    set gameTab to do script "{command}"
    set gameTty to tty of gameTab
    -- Before the row and column counts, so those are settled against the final
    -- character size and a window too big for the display is caught at startup.
    set font size of gameTab to {font_size}
    set background color of gameTab to {background}
    set number of rows of gameTab to {rows}
    set number of columns of gameTab to {cols}
    -- Otherwise the title bar shows the --child --sentinel plumbing.
    set custom title of gameTab to "{title}"
    set title displays custom title of gameTab to true
    set title displays shell path of gameTab to false
    set title displays device name of gameTab to false
    set title displays window size of gameTab to false
    set windowId to 0
    repeat with w in windows
        -- Terminal keeps closed windows in this list for a while as husks with
        -- no tabs; touching their tabs raises, so guard every one.
        try
            repeat with t in tabs of w
                if tty of t is gameTty then set windowId to id of w
            end repeat
        end try
    end repeat

    -- Same size, new position: the row and column counts settled the size
    -- already, and changing it here would resize the playfield out from under
    -- a game that has started drawing into it.
    if anchorBounds is not missing value and windowId is not 0 then
        try
            tell window id windowId
                set b to bounds
                set wd to (item 3 of b) - (item 1 of b)
                set ht to (item 4 of b) - (item 2 of b)
                set nx to (item 1 of anchorBounds) + {offset}
                set ny to (item 2 of anchorBounds) + {offset}
                set bounds to {{nx, ny, nx + wd, ny + ht}}
            end tell
        end try
    end if

    activate
    return windowId
end tell
'''

_CLOSE_SCRIPT = '''
tell application "Terminal"
    repeat with w in windows
        try
            if id of w is {window_id} then
                set isBusy to false
                try
                    set isBusy to busy of selected tab of w
                end try
                if not isBusy then close w
            end if
        end try
    end repeat
end tell
'''

# After the game writes its exit code it still has to unwind and exit. Closing
# the window before then makes Terminal prompt to terminate a running process,
# which blocks AppleScript on a modal dialog, so we wait the process out first.
CHILD_EXIT_TIMEOUT_SECONDS = 5.0


class LaunchError(RuntimeError):
    """Raised when the game window could not be opened."""


def is_supported() -> bool:
    """True when we can drive Terminal.app on this machine."""
    return sys.platform == "darwin" and os.path.exists("/usr/bin/osascript")


# -- sentinel file, the child's side ---------------------------------------


def announce_started(sentinel_path: Optional[str]) -> None:
    """Called by the child once it is running, so the launcher can watch it."""
    _write_sentinel(sentinel_path, "pid {}".format(os.getpid()))


def announce_finished(sentinel_path: Optional[str], exit_code: int) -> None:
    """Called by the child on the way out, cleanly or otherwise."""
    _write_sentinel(sentinel_path, "exit {}".format(exit_code))


def _write_sentinel(sentinel_path: Optional[str], text: str) -> None:
    if not sentinel_path:
        return
    try:
        # Write-and-rename so the launcher never reads a half-written file.
        temporary = sentinel_path + ".tmp"
        with open(temporary, "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, sentinel_path)
    except OSError:
        pass  # the launcher's liveness check covers us


# -- launcher side ----------------------------------------------------------


def launch(rows: int, cols: int, child_arguments: List[str]) -> int:
    """Open the game in a new window and block until it exits.

    Returns the game's exit code.
    """
    if os.environ.get(ENV_CHILD) == "1":
        # We are already inside a window this launcher opened. Spawning again
        # would recurse, and each generation opens a real window, so refuse
        # outright rather than trusting every caller to detect its own role.
        raise LaunchError(
            "Refusing to spawn: this process is already the spawned child "
            "({}=1). The caller should be running the game, not relaunching "
            "it.".format(ENV_CHILD)
        )

    if not is_supported():
        raise LaunchError(
            "Spawning a window needs macOS with Terminal.app. "
            "Run with --here to play in this terminal instead."
        )

    directory = tempfile.mkdtemp(prefix="terminalgame-")
    sentinel = os.path.join(directory, "sentinel")
    try:
        command = _build_command(sentinel, child_arguments)
        window_id = _spawn_window(command, rows, cols)
        exit_code, child_pid = _wait_for_child(sentinel)
        if child_pid is not None:
            _wait_for_process_exit(child_pid)
        if window_id:
            _close_window(window_id)
        return exit_code
    finally:
        _cleanup(directory, sentinel)


def _build_command(sentinel: str, child_arguments: List[str]) -> str:
    """The shell line Terminal will run in the new window.

    `exec` replaces the shell with Python, so when the game exits the tab has
    no running process and closes without Terminal asking for confirmation.
    """
    parts = [
        "cd",
        shlex.quote(_project_root()),
        "&&",
        "clear",
        "&&",
        "{}=1".format(ENV_CHILD),
        "{}={}".format(ENV_SENTINEL, shlex.quote(sentinel)),
        "exec",
        shlex.quote(sys.executable),
        "-m",
        MAIN_MODULE,
    ] + [shlex.quote(argument) for argument in child_arguments]
    return " ".join(parts)


def _project_root() -> str:
    """The directory holding the `terminalgame` package.

    Derived from this file rather than sys.argv[0], which under `-m` points at
    the module inside the package and would put the child in the wrong cwd.
    """
    return os.path.dirname(  # <root>
        os.path.dirname(     # <root>/terminalgame
            os.path.dirname(os.path.abspath(__file__))  # <root>/terminalgame/app
        )
    )


def _spawn_window(command: str, rows: int, cols: int) -> int:
    # The command is embedded in an AppleScript string literal, so backslashes
    # and double quotes have to survive one more level of escaping.
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    script = _SPAWN_SCRIPT.format(
        command=escaped, rows=rows, cols=cols, title=WINDOW_TITLE,
        font_size=FONT_SIZE, background=BACKGROUND_COLOR,
        offset=WINDOW_OFFSET,
    )
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise LaunchError("Terminal.app refused to open the window: {}".format(
            (error.stderr or "").strip()
        ))
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0  # window opened but we could not identify it; just don't close it


def _wait_for_child(sentinel: str) -> Tuple[int, Optional[int]]:
    """Block until the game reports an exit code, or its process disappears.

    Returns (exit code, child pid) -- the pid so the caller can wait for the
    process to actually leave before touching its window.
    """
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    child_pid = None

    while True:
        state, value = _read_sentinel(sentinel)

        if state == "exit":
            return value, child_pid
        if state == "pid":
            child_pid = value
        elif child_pid is None and time.monotonic() > deadline:
            raise LaunchError(
                "The game window did not start within {:.0f}s.".format(
                    STARTUP_TIMEOUT_SECONDS
                )
            )

        if child_pid is not None and not _process_alive(child_pid):
            # Window closed from under the game, or it was killed outright.
            return 0, None

        time.sleep(POLL_INTERVAL_SECONDS)


def _wait_for_process_exit(pid: int) -> None:
    """Wait, briefly and bounded, for the game process to disappear."""
    deadline = time.monotonic() + CHILD_EXIT_TIMEOUT_SECONDS
    while _process_alive(pid) and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS / 2)


def _read_sentinel(sentinel: str) -> Tuple[Optional[str], int]:
    try:
        with open(sentinel) as handle:
            state, _, raw = handle.read().strip().partition(" ")
        return state, int(raw)
    except (OSError, ValueError):
        return None, 0


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _close_window(window_id: int) -> None:
    subprocess.run(
        ["/usr/bin/osascript", "-e", _CLOSE_SCRIPT.format(window_id=window_id)],
        capture_output=True,
        text=True,
    )


def _cleanup(directory: str, sentinel: str) -> None:
    for path in (sentinel, sentinel + ".tmp"):
        try:
            os.unlink(path)
        except OSError:
            pass
    try:
        os.rmdir(directory)
    except OSError:
        pass
