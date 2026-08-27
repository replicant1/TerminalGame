"""Terminal front end: the only code that knows about curses and Terminal.app.

`screen` paints ViewStates and reads the keyboard. Nothing here is imported by
the game logic -- the dependency runs one way, from the UI towards the
ViewModel, never back.
"""

from .screen import GameScreen, TerminalTooSmall

__all__ = ["GameScreen", "TerminalTooSmall"]
