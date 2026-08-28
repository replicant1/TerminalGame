#!/usr/bin/env python3
"""Drive the game headlessly: a pty for the terminal, pyte for the screen.

The game is a curses app, so it needs a real terminal to run in and something
that understands escape codes to read it back. This gives it both without a
window: pty.fork() supplies the terminal, pyte replays what curses writes into
a 30x40 character grid that `show` prints.

    ./driver.py <<'EOF'          # commands on stdin, one per line
    show start
    right 4
    down 2
    show moved
    quit
    EOF

Commands
    show [label]       print the current 30x40 screen, boxed
    status             print just the status line (bottom row)
    up|down|left|right [n]   arrow key, n times (default 1)
    key <text>         send literal characters, e.g. `key q`
    esc                send Esc (quits the game)
    wait <seconds>     let the clock run
    quit               send q, wait for exit, report the exit code

Every command settles for SETTLE seconds afterwards so the ticks it caused
land before the next `show`. The driver exits with the game's own exit code,
or 1 if a command was malformed.
"""

import errno
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time

# The playfield is exactly this. Sized on the pty before the game measures it,
# or GameScreen raises TerminalTooSmall and exits 1.
ROWS, COLS = 30, 40

# Long enough for a few 0.15s ticks to land and be rendered.
SETTLE = 0.6

# How long to let the game notice the pty hanging up before resorting to
# SIGKILL. It normally exits within 0.1s.
HANGUP_GRACE = 2.0

# Arrow keys in APPLICATION cursor mode -- ESC O C, not ESC [ C. keypad(True)
# sends smkx at startup, which puts the terminal in that mode; ncurses then
# only recognises this form. See Gotchas in SKILL.md: the CSI form is decoded
# as a bare Esc, which the game treats as quit.
ARROWS = {
    "up": b"\x1bOA",
    "down": b"\x1bOB",
    "right": b"\x1bOC",
    "left": b"\x1bOD",
}

class Bad(Exception):
    """A command the driver could not make sense of."""


# Set on the child of the one permitted bootstrap re-exec, so a venv that
# cannot produce a working pyte fails loudly instead of looping.
RE_EXECED = "TERMINALGAME_DRIVER_REEXECED"

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))
VENV = os.path.join(SKILL_DIR, ".venv")


def has_pyte(python):
    """Can that interpreter import pyte? Cheaper than a pip run per invocation."""
    if not os.path.exists(python):
        return False
    return subprocess.run([python, "-c", "import pyte"],
                          capture_output=True).returncode == 0


def ensure_pyte():
    """Import pyte, building a private venv for it on first run.

    The install runs whenever the import fails, not only when the venv is
    missing -- a venv that exists but has lost pyte is otherwise a re-exec into
    an interpreter that fails the same import, forever. RE_EXECED caps it at
    one re-exec whatever happens.
    """
    try:
        import pyte  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get(RE_EXECED):
        sys.exit("driver: pyte still missing after installing it into {}.\n"
                 "Delete that directory and run again.".format(VENV))
    venv_python = os.path.join(VENV, "bin", "python")
    if not has_pyte(venv_python):
        # Reached on the first run, and again if the venv loses pyte -- but not
        # on every run merely because the *calling* interpreter lacks it.
        if not os.path.exists(venv_python):
            print("driver: creating {}".format(VENV), file=sys.stderr)
            subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
        print("driver: installing pyte into {}".format(VENV), file=sys.stderr)
        subprocess.run(
            [venv_python, "-m", "pip", "--quiet", "--disable-pip-version-check",
             "install", "pyte"],
            check=True,
        )
    os.environ[RE_EXECED] = "1"
    os.execv(venv_python, [venv_python, os.path.abspath(__file__)] + sys.argv[1:])


ensure_pyte()
import pyte  # noqa: E402


class Game:
    def __init__(self):
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)
        self.exit_code = None
        # The child must not reach GameScreen.open() -- which measures the
        # terminal and raises TerminalTooSmall if it is short -- before the
        # parent has sized the pty. Sizing happens after the fork, so the child
        # blocks on this pipe until the parent says the size is in place.
        sized_read, sized_write = os.pipe()
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # child: become the game
            try:
                os.close(sized_write)
                os.read(sized_read, 1)
                os.close(sized_read)
                os.chdir(PROJECT_ROOT)
                os.environ["TERM"] = "xterm-256color"
                # ncurses prefers LINES/COLUMNS over the pty's real size, so an
                # exported pair in the calling shell would mask it and go stale
                # on resize. Dropped rather than merely left unset.
                os.environ.pop("LINES", None)
                os.environ.pop("COLUMNS", None)
                os.execvp("python3", ["python3", "-m", "terminalgame.app.main", "--here"])
            except BaseException:
                os._exit(127)  # never unwind past the fork
        os.close(sized_read)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
        os.write(sized_write, b"1")
        os.close(sized_write)

    def pump(self, seconds):
        """Feed the emulator for `seconds`, noticing if the game exits."""
        end = time.time() + seconds
        while time.time() < end:
            if self.exit_code is not None:
                return
            readable, _, _ = select.select([self.fd], [], [], max(0, end - time.time()))
            if not readable:
                continue
            try:
                data = os.read(self.fd, 65536)
            except OSError as error:
                # EIO on the master is how the kernel reports the child gone;
                # anything else is a real fault and must not read as EOF.
                if error.errno != errno.EIO:
                    raise
                data = b""
            if not data:
                self.reap()
                return
            self.stream.feed(data)

    def send(self, data, settle=SETTLE):
        try:
            os.write(self.fd, data)
        except OSError as error:
            if error.errno != errno.EIO:
                raise
            self.reap()
            return
        self.pump(settle)

    def reap(self):
        if self.exit_code is None:
            try:
                _, status = os.waitpid(self.pid, 0)
            except ChildProcessError:
                self.exit_code = 128
                return
            self.exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128

    def kill(self):
        """Make sure the game is gone. A no-op once it has exited.

        SIGTERM is no use here: ncurses installs its own handler at initscr()
        so it can restore the terminal, and the game sits straight through it
        (`ps` keeps reporting `Ss+` seconds later). Closing the master hangs
        the pty up, which it does notice -- measured at 0.1s -- and SIGKILL is
        the backstop for a game wedged somewhere that cannot notice either.
        """
        try:
            os.close(self.fd)
        except OSError:
            pass
        if self.exit_code is None:
            deadline = time.time() + HANGUP_GRACE
            while time.time() < deadline:
                pid, status = os.waitpid(self.pid, os.WNOHANG)
                if pid:
                    self.exit_code = (os.WEXITSTATUS(status) if os.WIFEXITED(status)
                                      else 128)
                    return
                time.sleep(0.05)
            try:
                os.kill(self.pid, signal.SIGKILL)
            except OSError:
                pass
            self.reap()

    def show(self, label=""):
        print("== {} ==".format(label) if label else "== frame ==")
        for line in self.screen.display:
            print("|" + line.rstrip().ljust(COLS) + "|")
        print()

    def status(self):
        print(self.screen.display[ROWS - 1].strip())


def dispatch(game, line):
    """Run one command. Returns False to stop the script."""
    word, _, rest = line.partition(" ")
    rest = rest.strip()
    if game.exit_code is not None and word != "show":
        print("driver: game already exited ({})".format(game.exit_code),
              file=sys.stderr)
        return False
    if word == "show":
        game.show(rest)
    elif word == "status":
        game.status()
    elif word in ARROWS:
        game.send(ARROWS[word] * count(rest))
    elif word == "key":
        game.send(rest.encode())
    elif word == "esc":
        game.send(b"\x1b")
    elif word == "wait":
        game.pump(seconds(rest))
    elif word == "quit":
        game.send(b"q", 1.0)
        game.reap()
    else:
        raise Bad("unknown command {!r}".format(word))
    return True


def count(rest):
    if not rest:
        return 1
    try:
        n = int(rest)
    except ValueError:
        raise Bad("expected a repeat count, got {!r}".format(rest))
    if n < 1:
        raise Bad("repeat count must be at least 1, got {}".format(n))
    return n


def seconds(rest):
    try:
        value = float(rest)
    except ValueError:
        raise Bad("expected a number of seconds, got {!r}".format(rest))
    if value < 0:
        raise Bad("seconds must not be negative, got {}".format(value))
    return value


def run(commands):
    game = Game()
    try:
        game.pump(1.5)  # startup: initscr, the resize request, the first paint
        for line in commands:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            try:
                if not dispatch(game, line):
                    break
            except Bad as error:
                print("driver: {} (in {!r})".format(error, line), file=sys.stderr)
                return 1
        if game.exit_code is None:
            game.send(b"q", 1.0)
            game.reap()
        print("exit code:", game.exit_code)
        # The game's own code, so a 127 from a failed exec and a 1 from
        # TerminalTooSmall stay told apart. Driver errors return 1 above.
        return game.exit_code
    finally:
        # Any exit -- bad command, exception, quit -- takes the game with it,
        # so nothing is left holding a pty.
        game.kill()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as handle:
            script = handle.read()
    else:
        script = sys.stdin.read()
    sys.exit(run(script.splitlines()))
