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
land before the next `show`. Exit code is the game's, or 1 if a command failed.
"""

import fcntl
import os
import pty
import re
import select
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

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))
VENV = os.path.join(SKILL_DIR, ".venv")


def ensure_pyte():
    """Import pyte, building a private venv for it on first run."""
    try:
        import pyte  # noqa: F401
        return
    except ImportError:
        pass
    venv_python = os.path.join(VENV, "bin", "python")
    if not os.path.exists(venv_python):
        print("driver: installing pyte into {}".format(VENV), file=sys.stderr)
        subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
        subprocess.run(
            [venv_python, "-m", "pip", "--quiet", "--disable-pip-version-check",
             "install", "pyte"],
            check=True,
        )
    os.execv(venv_python, [venv_python, os.path.abspath(__file__)] + sys.argv[1:])


ensure_pyte()
import pyte  # noqa: E402


class Game:
    def __init__(self):
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)
        self.exit_code = None
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # child: become the game
            os.chdir(PROJECT_ROOT)
            os.environ["TERM"] = "xterm-256color"
            # LINES/COLUMNS are deliberately NOT set -- ncurses prefers them
            # over the pty's real size and they go stale on resize.
            os.execvp("python3", ["python3", "-m", "terminalgame.app.main", "--here"])
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

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
            except OSError:
                data = b""  # macOS: EIO on the master once the child is gone
            if not data:
                self.reap()
                return
            self.stream.feed(data)

    def send(self, data, settle=SETTLE):
        try:
            os.write(self.fd, data)
        except OSError:
            self.reap()
            return
        self.pump(settle)

    def reap(self):
        if self.exit_code is None:
            _, status = os.waitpid(self.pid, 0)
            self.exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128

    def show(self, label=""):
        print("== {} ==".format(label) if label else "== frame ==")
        for line in self.screen.display:
            print("|" + line.rstrip().ljust(COLS) + "|")
        print()

    def status(self):
        print(self.screen.display[ROWS - 1].strip())


def run(commands):
    game = Game()
    game.pump(1.5)  # startup: initscr, the resize request, the first paint
    for line in commands:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        word, _, rest = line.partition(" ")
        rest = rest.strip()
        if game.exit_code is not None and word != "show":
            print("driver: game already exited ({})".format(game.exit_code),
                  file=sys.stderr)
            break
        if word == "show":
            game.show(rest)
        elif word == "status":
            game.status()
        elif word in ARROWS:
            game.send(ARROWS[word] * int(rest or 1))
        elif word == "key":
            game.send(rest.encode())
        elif word == "esc":
            game.send(b"\x1b")
        elif word == "wait":
            game.pump(float(rest))
        elif word == "quit":
            game.send(b"q", 1.0)
            game.reap()
        else:
            print("driver: unknown command {!r}".format(line), file=sys.stderr)
            return 1
    if game.exit_code is None:
        game.send(b"q", 1.0)
        game.reap()
    print("exit code:", game.exit_code)
    return 0 if game.exit_code == 0 else 1


if __name__ == "__main__":
    source = open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin
    sys.exit(run(source.read().splitlines()))
