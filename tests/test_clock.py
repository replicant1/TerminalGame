"""GameClock: fires on a deadline the caller polls, and never drifts.

Real time is never waited on. The module's `time` is swapped for a fake whose
`monotonic` returns whatever the test last set, so a whole session's worth of
ticks costs nothing and always lands on the same numbers.
"""

import unittest
from unittest import mock

from terminalgame.util import clock as clock_module
from terminalgame.util.clock import GameClock


class FakeTime:
    """Stands in for the `time` module, with a clock the test winds by hand."""

    def __init__(self, now=0.0):
        self.now = now

    def monotonic(self):
        return self.now


class GameClockTest(unittest.TestCase):

    def setUp(self):
        self.time = FakeTime()
        patcher = mock.patch.object(clock_module, "time", self.time)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ticks = []
        self.clock = GameClock(1.0, lambda: self.ticks.append(self.time.now))

    def test_a_new_clock_is_not_running(self):
        self.assertFalse(self.clock.running)

    def test_a_stopped_clock_fires_nothing_however_late_it_gets(self):
        self.time.now = 1000.0

        self.assertEqual(0, self.clock.poll())
        self.assertEqual([], self.ticks)

    def test_starting_makes_it_run(self):
        self.clock.start()

        self.assertTrue(self.clock.running)

    def test_no_tick_fires_before_the_first_interval_is_up(self):
        self.clock.start()
        self.time.now = 0.999

        self.assertEqual(0, self.clock.poll())
        self.assertEqual([], self.ticks)

    def test_a_tick_fires_once_the_interval_is_up(self):
        self.clock.start()
        self.time.now = 1.0

        self.assertEqual(1, self.clock.poll())
        self.assertEqual([1.0], self.ticks)

    def test_a_backlog_of_two_fires_twice_and_leaves_the_deadline_undrifted(self):
        """Deadlines advance by whole intervals, so the rate cannot slip.

        Two and a half intervals late, the third tick is still due half an
        interval from now -- not a whole one, which is what resetting the
        deadline to `now` would give.
        """
        self.clock.start()
        self.time.now = 2.5

        self.assertEqual(2, self.clock.poll())
        self.assertEqual([2.5, 2.5], self.ticks)
        self.assertAlmostEqual(0.5, self.clock.seconds_until_next_tick())

    def test_a_tick_that_stops_the_clock_is_the_last_one_to_fire(self):
        """Otherwise stop() means "after this backlog", which is not what it says."""
        self.clock = GameClock(1.0, lambda: (self.ticks.append(self.time.now),
                                             self.clock.stop()))
        self.clock.start()
        self.time.now = 3.0  # three ticks outstanding

        fired = self.clock.poll()

        self.assertEqual(1, fired)
        self.assertEqual(1, len(self.ticks))

    def test_a_long_suspension_fires_at_most_the_catch_up_limit(self):
        """Ctrl-Z or a laptop sleep must not replay hours of missed ticks."""
        self.clock.start()
        self.time.now = 100.0

        fired = self.clock.poll()

        self.assertEqual(GameClock.MAX_CATCH_UP_TICKS, fired)
        self.assertEqual(GameClock.MAX_CATCH_UP_TICKS, len(self.ticks))

    def test_a_long_suspension_resynchronises_instead_of_staying_behind(self):
        """After the cap, the next tick is a full interval away again.

        Without the realignment the deadline would still be back at 4.0 and
        the very next poll would fire another three, and another, until it had
        crawled all the way to the present.
        """
        self.clock.start()
        self.time.now = 100.0
        self.clock.poll()

        self.assertAlmostEqual(1.0, self.clock.seconds_until_next_tick())
        self.assertEqual(0, self.clock.poll(), "still replaying the backlog")

    def test_stopping_silences_the_clock(self):
        self.clock.start()
        self.clock.stop()
        self.time.now = 50.0

        self.assertFalse(self.clock.running)
        self.assertEqual(0, self.clock.poll())
        self.assertEqual([], self.ticks)

    def test_restarting_measures_the_first_tick_from_the_restart(self):
        self.clock.start()
        self.clock.stop()
        self.time.now = 50.0
        self.clock.start()

        self.assertEqual(0, self.clock.poll(), "fired on a deadline from before the stop")
        self.time.now = 51.0
        self.assertEqual(1, self.clock.poll())

    def test_a_stopped_clock_offers_a_whole_interval_as_an_input_timeout(self):
        self.assertEqual(1.0, self.clock.seconds_until_next_tick())

    def test_the_wait_shrinks_as_the_deadline_approaches(self):
        self.clock.start()
        self.time.now = 0.25

        self.assertAlmostEqual(0.75, self.clock.seconds_until_next_tick())

    def test_the_wait_is_never_negative(self):
        """A caller passes this to getch() as a timeout, which cannot be negative."""
        self.clock.start()
        self.time.now = 7.0

        self.assertEqual(0.0, self.clock.seconds_until_next_tick())


if __name__ == "__main__":
    unittest.main()
