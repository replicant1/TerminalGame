"""Fixed-timestep game clock.

Implemented as a monotonic deadline polled from the main loop rather than a
threading.Timer, because curses is not thread-safe -- a tick arriving on a
background thread while the main thread is mid-refresh corrupts the screen.
Polling keeps the entire game single-threaded.
"""

import time
from typing import Callable


class GameClock:
    """Calls a callback once every interval, driven by poll().

    Nothing here runs on its own: the clock only advances when the main loop
    polls it, which is what keeps ticks on the same thread as the rendering.
    """

    # If the process is suspended (Ctrl-Z, laptop sleep), don't try to replay
    # hours of missed ticks -- fire at most this many, then resynchronise.
    MAX_CATCH_UP_TICKS = 3

    def __init__(self, interval_seconds: float, on_tick: Callable[[], None]) -> None:
        """Prepares a clock. It does not start ticking until `start`.

        Args:
            interval_seconds: How long one tick lasts.
            on_tick: Called once per tick, from whatever thread calls `poll`.
        """
        self._interval = interval_seconds
        self._on_tick = on_tick
        self._next_deadline = 0.0
        self._running = False

    @property
    def running(self) -> bool:
        """Whether the clock is ticking, so between `start` and `stop`."""
        return self._running

    def start(self) -> None:
        """Begins ticking, with the first tick one full interval from now."""
        self._next_deadline = time.monotonic() + self._interval
        self._running = True

    def stop(self) -> None:
        """Stops ticking. `poll` fires nothing until `start` is called again."""
        self._running = False

    def seconds_until_next_tick(self) -> float:
        """Returns how long until the next tick is due.

        Returns:
            Seconds until the deadline, never negative, and one whole interval
            while the clock is stopped -- a caller waiting on input can use it
            as a timeout either way.
        """
        if not self._running:
            return self._interval
        return max(0.0, self._next_deadline - time.monotonic())

    def poll(self) -> int:
        """Fires any ticks that are due.

        Advancing the deadline by whole intervals (rather than resetting it to
        `now`) stops the tick rate drifting slower over a long session.

        Returns:
            How many ticks fired, at most MAX_CATCH_UP_TICKS. Zero while the
            clock is stopped.
        """
        if not self._running:
            return 0

        fired = 0
        while time.monotonic() >= self._next_deadline:
            self._next_deadline += self._interval
            fired += 1
            self._on_tick()
            if fired >= self.MAX_CATCH_UP_TICKS:
                # Drop whatever backlog remains and realign to the present.
                if time.monotonic() >= self._next_deadline:
                    self._next_deadline = time.monotonic() + self._interval
                break
        return fired
