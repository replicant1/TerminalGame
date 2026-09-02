#!/usr/bin/env python3
"""Entry point.

    python3 -m terminalgame.app.main           # opens the game in its own 30x40 window
    python3 -m terminalgame.app.main --here    # runs in the current terminal instead

Without --here the process re-launches itself inside a new Terminal.app window
(see terminalgame/app/launcher.py), then blocks until the game exits and forwards its exit
code, so it still behaves like an ordinary command.
"""

import argparse
import curses
import os
import sys

from .. import (
    GameClock,
    GameScreen,
    GameViewModel,
    TerminalTooSmall,
)
from ..presentation.state import PLAYFIELD_COLS, PLAYFIELD_ROWS
from . import launcher

# The simulation step. Roughly 1 / 7 of a second -- fast enough for the ghost
# to read as moving rather than teleporting.
TICK_INTERVAL_SECONDS = 0.15

# How long getch() may block before we check the clock again. This is the input
# latency, not the frame rate -- keys are rendered the moment they arrive.
INPUT_POLL_MILLISECONDS = 33

_DIRECTIONS = {
    curses.KEY_UP: (-1, 0),
    curses.KEY_DOWN: (1, 0),
    curses.KEY_LEFT: (0, -1),
    curses.KEY_RIGHT: (0, 1),
}
_QUIT_KEYS = {ord("q"), ord("Q"), 27}  # 27 = Esc


def run(screen: GameScreen) -> None:
    """Runs the game loop until the player quits.

    Keys are handled the moment they arrive and the clock is polled between
    them, so ticks and rendering stay on this one thread.

    Args:
        screen: An open screen to draw on and read keys from.
    """
    view_model = GameViewModel()
    clock = GameClock(TICK_INTERVAL_SECONDS, view_model.tick)

    # Subscribing paints the initial frame immediately.
    screen.attach(view_model)
    screen.set_input_timeout(INPUT_POLL_MILLISECONDS)
    clock.start()

    while True:
        key = screen.read_key()

        if key is not None:
            if key in _QUIT_KEYS:
                return
            if key == curses.KEY_RESIZE:
                screen.handle_resize()
                screen.render(view_model.state.value)
            elif key in _DIRECTIONS:
                view_model.on_direction(*_DIRECTIONS[key])

        # Fires view_model.tick(), which publishes a new ViewState, which the
        # screen is already subscribed to. Nothing here touches the terminal.
        clock.poll()


def play(sentinel: str, spawned: bool) -> int:
    """Plays the game in whatever terminal this process already owns.

    Args:
        sentinel: File to report progress to, or None when nothing is
            watching.
        spawned: Whether this process is running inside a window the launcher
            opened, which is what decides if an error has to be held on screen
            before the window closes.

    Returns:
        0 for a normal exit, 1 if the terminal was too small to play in or
        the game fell over.
    """
    launcher.announce_started(sentinel)
    # A crash must not reach the sentinel as success, so 1 is what an
    # unhandled exception leaves behind: only the endings below clear it.
    exit_code = 1
    try:
        with GameScreen() as screen:
            run(screen)
        exit_code = 0
    except TerminalTooSmall as error:
        print(error, file=sys.stderr)
        if spawned:
            # The launcher closes this window the moment we exit, so hold it
            # open long enough for the message to be read.
            _pause("Press Return to close this window.")
    except KeyboardInterrupt:
        exit_code = 0
    finally:
        launcher.announce_finished(sentinel, exit_code)
    return exit_code


def _pause(message: str) -> None:
    """Holds the window open until Return is pressed.

    Args:
        message: What to tell the player before waiting.
    """
    try:
        input("\n" + message)
    except (EOFError, KeyboardInterrupt):
        pass


def parse_arguments(argv):
    """Reads the command line, falling back to the launcher's environment.

    Args:
        argv: Arguments to parse, or None to take them from sys.argv.

    Returns:
        The parsed arguments, with `child` and `sentinel` filled in from the
        environment when the launcher set them there rather than in argv.
    """
    parser = argparse.ArgumentParser(description="A retro terminal game skeleton.")
    parser.add_argument(
        "--here",
        action="store_true",
        help="run in the current terminal instead of spawning a new window",
    )
    # Normally set by the launcher through the environment when it re-invokes
    # us inside the new window; the flags exist so the child can be run by hand.
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--sentinel", default=None, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    arguments.child = arguments.child or os.environ.get(launcher.ENV_CHILD) == "1"
    if arguments.sentinel is None:
        arguments.sentinel = os.environ.get(launcher.ENV_SENTINEL)
    return arguments


def main(argv=None) -> int:
    """Plays the game here, or opens a window and plays it there.

    Args:
        argv: Arguments to parse, or None to take them from sys.argv.

    Returns:
        The game's exit code, or 1 if the window could not be opened.
    """
    arguments = parse_arguments(argv)

    if arguments.child or arguments.here:
        return play(arguments.sentinel, spawned=arguments.child)

    try:
        return launcher.launch(PLAYFIELD_ROWS, PLAYFIELD_COLS, [])
    except launcher.LaunchError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
