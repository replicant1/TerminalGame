"""The game loop and the command line.

The loop is the one piece nothing else covers: no assertion about state can
tell "the loop handled the key" from "the loop never ran". So it is driven for
real here, against a screen with a scripted keyboard and a seeded ViewModel.
"""

import curses
import functools
import io
import os
import unittest
from unittest import mock

from terminalgame.app import main as main_module
from terminalgame.app.main import parse_arguments, play, run
from terminalgame.presentation.state import COLOR_PLAYER
from terminalgame.presentation.view_model import GameViewModel
from terminalgame.ui.screen import TerminalTooSmall

from .fakes import FakeScreen, LoopDidNotQuit
from .test_view_model import STEPS, has_pill, player_cell

SEED = 1
ARROWS = {
    (-1, 0): curses.KEY_UP,
    (1, 0): curses.KEY_DOWN,
    (0, -1): curses.KEY_LEFT,
    (0, 1): curses.KEY_RIGHT,
}
QUIT = ord("q")


def seeded_view_model():
    """Patches the loop's ViewModel so its maze is the same one every run."""
    return mock.patch.object(
        main_module, "GameViewModel", functools.partial(GameViewModel, seed=SEED)
    )


class GameLoopTest(unittest.TestCase):

    def setUp(self):
        # The same maze the loop will build, so the test knows which way is open.
        reference = GameViewModel(seed=SEED).state.value
        self.start = player_cell(reference)
        self.open_step = next(
            step for step in STEPS
            if has_pill(reference, self.start[0] + step[0], self.start[1] + step[1])
        )
        self.blocked_step = next(
            step for step in STEPS
            if not has_pill(reference, self.start[0] + step[0], self.start[1] + step[1])
        )

    def play(self, keys, idle_reads=0):
        screen = FakeScreen(keys=keys, idle_reads=idle_reads)
        with seeded_view_model():
            run(screen)
        return screen

    def test_q_ends_the_game(self):
        screen = self.play([QUIT])

        self.assertEqual(1, len(screen.frames), "the loop ran on past the quit key")

    def test_the_uppercase_and_escape_keys_quit_too(self):
        for key in (ord("Q"), 27):
            self.play([key])  # would raise LoopDidNotQuit if it kept reading

    def test_the_opening_frame_is_painted_before_any_key_arrives(self):
        screen = self.play([QUIT])

        self.assertEqual(0, screen.frames[0].tick)

    def test_the_input_timeout_is_set_before_the_first_read(self):
        """Without it getch blocks forever and the clock is never polled."""
        screen = self.play([QUIT])

        self.assertEqual(main_module.INPUT_POLL_MILLISECONDS, screen.timeout)

    def test_an_arrow_key_moves_the_player(self):
        screen = self.play([ARROWS[self.open_step], QUIT])

        self.assertEqual(
            (self.start[0] + self.open_step[0], self.start[1] + self.open_step[1]),
            player_cell(screen.frames[-1]),
        )

    def test_an_arrow_key_repaints_the_screen(self):
        screen = self.play([ARROWS[self.open_step], QUIT])

        self.assertEqual(2, len(screen.frames))

    def test_an_arrow_key_into_a_wall_repaints_nothing(self):
        screen = self.play([ARROWS[self.blocked_step], QUIT])

        self.assertEqual(1, len(screen.frames))

    def test_a_key_the_game_does_not_use_is_ignored(self):
        screen = self.play([ord("z"), ord("!"), QUIT])

        self.assertEqual(1, len(screen.frames))

    def test_no_key_at_all_is_not_mistaken_for_one(self):
        """read_key returns None on a timeout, and None is not a quit key."""
        screen = self.play([QUIT], idle_reads=0)

        self.assertEqual(1, len(screen.frames))

    def test_the_loop_keeps_reading_when_no_key_arrives(self):
        """A timeout with nothing typed must not be taken as a reason to stop."""
        screen = FakeScreen(keys=[], idle_reads=3)

        with seeded_view_model(), self.assertRaises(LoopDidNotQuit):
            run(screen)

        self.assertEqual(0, screen.idle_reads, "it gave up before the third timeout")

    def test_a_resize_re_measures_and_repaints_the_current_frame(self):
        """The frame has not changed, so only an explicit repaint can show it."""
        screen = self.play([curses.KEY_RESIZE, QUIT])

        self.assertEqual(1, screen.resizes)
        self.assertEqual(2, len(screen.frames))
        self.assertEqual(screen.frames[0], screen.frames[1])

    def test_the_clock_is_polled_between_keys_so_the_ghost_moves(self):
        """With no interval every poll is due, which proves the poll happens."""
        screen = FakeScreen(keys=[ord("z"), ord("z"), QUIT])
        with seeded_view_model(), \
                mock.patch.object(main_module, "TICK_INTERVAL_SECONDS", 0.0):
            run(screen)

        self.assertGreater(screen.frames[-1].tick, 0, "the clock was never polled")

    def test_the_ghost_stands_still_while_the_clock_has_not_fired(self):
        """The real interval is 0.15s and the test loop takes microseconds."""
        screen = self.play([QUIT])

        self.assertEqual(0, screen.frames[-1].tick)


class PlayTest(unittest.TestCase):
    """What `play` reports to the launcher, whichever way the game ends."""

    def fake_screen_factory(self, error=None):
        class FakeGameScreen:
            def __enter__(inner):
                if error is not None:
                    raise error
                return inner

            def __exit__(inner, *exception):
                return False

        return FakeGameScreen

    def play_with(self, screen_factory, run_impl=lambda screen: None, spawned=False):
        # Kept on the instance as well as returned, so a test whose game
        # raises can still read what the launcher was told on the way out.
        self.announced = []
        with mock.patch.object(main_module, "GameScreen", screen_factory), \
                mock.patch.object(main_module, "run", run_impl), \
                mock.patch.object(main_module.launcher, "announce_started",
                                  lambda path: self.announced.append(("started", path))), \
                mock.patch.object(main_module.launcher, "announce_finished",
                                  lambda path, code: self.announced.append(("finished", code))), \
                mock.patch.object(main_module.sys, "stderr", io.StringIO()):
            code = play("/tmp/sentinel", spawned=spawned)
            return code, self.announced, main_module.sys.stderr.getvalue()

    def test_a_normal_game_exits_zero(self):
        code, announced, _ = self.play_with(self.fake_screen_factory())

        self.assertEqual(0, code)
        self.assertEqual([("started", "/tmp/sentinel"), ("finished", 0)], announced)

    def test_a_terminal_too_small_exits_one_and_says_why(self):
        error = TerminalTooSmall("Need at least 30x40; terminal is 10x20.")

        code, announced, stderr = self.play_with(self.fake_screen_factory(error))

        self.assertEqual(1, code)
        self.assertIn("10x20", stderr)
        self.assertIn(("finished", 1), announced)

    def test_ctrl_c_is_a_normal_way_to_stop_playing(self):
        def interrupt(screen):
            raise KeyboardInterrupt

        code, announced, _ = self.play_with(self.fake_screen_factory(), interrupt)

        self.assertEqual(0, code)
        self.assertIn(("finished", 0), announced)

    def test_a_game_that_falls_over_is_reported_as_a_failure(self):
        """Otherwise `python3 -m terminalgame.app.main && echo OK` prints OK."""
        def explode(screen):
            raise ZeroDivisionError("mid-game")

        with self.assertRaises(ZeroDivisionError):
            self.play_with(self.fake_screen_factory(), explode)

        self.assertIn(("finished", 1), self.announced)


class ArgumentTest(unittest.TestCase):

    def parse(self, argv, environment=None):
        with mock.patch.dict(os.environ, environment or {}, clear=True):
            return parse_arguments(argv)

    def test_by_default_the_game_gets_its_own_window(self):
        arguments = self.parse([])

        self.assertFalse(arguments.here)
        self.assertFalse(arguments.child)

    def test_here_keeps_the_game_in_this_terminal(self):
        self.assertTrue(self.parse(["--here"]).here)

    def test_the_launcher_marks_the_child_through_the_environment(self):
        """The flags stay out of argv so they stay out of the window title."""
        arguments = self.parse([], {"TERMINALGAME_CHILD": "1"})

        self.assertTrue(arguments.child)

    def test_the_sentinel_path_is_taken_from_the_environment(self):
        arguments = self.parse([], {"TERMINALGAME_SENTINEL": "/tmp/s"})

        self.assertEqual("/tmp/s", arguments.sentinel)

    def test_an_explicit_sentinel_beats_the_environment(self):
        arguments = self.parse(["--sentinel", "/tmp/argv"],
                               {"TERMINALGAME_SENTINEL": "/tmp/env"})

        self.assertEqual("/tmp/argv", arguments.sentinel)

    def test_no_sentinel_anywhere_means_nobody_is_watching(self):
        self.assertIsNone(self.parse([]).sentinel)

    def test_the_child_flag_can_still_be_given_by_hand(self):
        self.assertTrue(self.parse(["--child"]).child)


class MainTest(unittest.TestCase):
    """Which of the two roles `main` takes, and what it does when spawning fails."""

    def test_here_plays_in_this_terminal_instead_of_spawning(self):
        with mock.patch.object(main_module, "play", return_value=0) as played, \
                mock.patch.object(main_module.launcher, "launch") as launched:
            code = main_module.main(["--here"])

        self.assertEqual(0, code)
        self.assertEqual(1, played.call_count)
        self.assertEqual(0, launched.call_count, "it spawned a window anyway")

    def test_the_game_forwards_its_own_exit_code(self):
        with mock.patch.object(main_module, "play", return_value=1):
            self.assertEqual(1, main_module.main(["--here"]))

    def test_the_child_plays_rather_than_spawning_another_window(self):
        with mock.patch.dict(os.environ, {"TERMINALGAME_CHILD": "1"}, clear=True), \
                mock.patch.object(main_module, "play", return_value=0) as played, \
                mock.patch.object(main_module.launcher, "launch") as launched:
            main_module.main([])

        self.assertEqual(0, launched.call_count)
        self.assertEqual({"spawned": True}, played.call_args[1])

    def test_with_no_arguments_a_window_is_opened_at_the_playfield_size(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(main_module.launcher, "launch", return_value=3) as launched:
            code = main_module.main([])

        self.assertEqual(3, code)
        self.assertEqual((30, 40, []), launched.call_args[0])

    def test_a_window_that_will_not_open_is_reported_rather_than_traced(self):
        failure = main_module.launcher.LaunchError("Terminal.app refused")
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(main_module.launcher, "launch", side_effect=failure), \
                mock.patch.object(main_module.sys, "stderr", io.StringIO()) as stderr:
            code = main_module.main([])

        self.assertEqual(1, code)
        self.assertIn("Terminal.app refused", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
