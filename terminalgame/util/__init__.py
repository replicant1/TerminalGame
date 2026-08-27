"""Game-agnostic plumbing: a fixed-timestep clock and a synchronous StateFlow.

Neither module knows what a playfield is, and neither imports curses. Both are
deliberately single-threaded -- curses is not thread-safe, so ticks and state
emissions all happen on the main loop's thread.
"""

from .clock import GameClock
from .flow import StateFlow

__all__ = ["GameClock", "StateFlow"]
