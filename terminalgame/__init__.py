"""Skeleton for a retro character-based terminal game."""

from .app import launcher
from .presentation.state import PLAYFIELD_COLS, PLAYFIELD_ROWS, Sprite, ViewState
from .presentation.view_model import GameViewModel
from .ui.screen import GameScreen, TerminalTooSmall
from .util.clock import GameClock
from .util.flow import StateFlow

__all__ = [
    "launcher",
    "GameClock",
    "GameScreen",
    "GameViewModel",
    "StateFlow",
    "Sprite",
    "ViewState",
    "TerminalTooSmall",
    "PLAYFIELD_ROWS",
    "PLAYFIELD_COLS",
]
