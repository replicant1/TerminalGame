"""GameScreen: what actually reaches the terminal, without one being attached.

Every test here drives the real GameScreen and reads back what it drew. curses
itself is either a fake module (for the lifecycle, which needs a real terminal)
or the real one with only `doupdate` held back (for drawing, which does not).
"""

import io
import unittest
from unittest import mock

from terminalgame.presentation.state import (
    COLOR_GHOST,
    COLOR_PILL,
    COLOR_PLAYER,
    COLOR_STATUS,
    COLOR_WALL,
    PLAYFIELD_COLS,
    PLAYFIELD_ROWS,
    Sprite,
    ViewState,
)
from terminalgame.presentation.view_model import GameViewModel
from terminalgame.ui import screen as screen_module
from terminalgame.ui.screen import GameScreen, TerminalTooSmall

from .fakes import FakeCurses, FakeWindow

# Distinct integers for the colour slots, so an assertion can say which colour
# a run was drawn in. The real screen fills this in from curses.init_pair.
PAIRS = {
    COLOR_WALL: 11,
    COLOR_PLAYER: 22,
    COLOR_GHOST: 33,
    COLOR_STATUS: 44,
    COLOR_PILL: 55,
}


def a_state(walls=("",), pills=("",), sprites=(), status_line=" score 0"):
    return ViewState(walls=tuple(walls), pills=tuple(pills), sprites=tuple(sprites),
                     status_line=status_line)


class RenderTest(unittest.TestCase):
    """Drawing needs no terminal, only somewhere to put the characters."""

    def setUp(self):
        self.window = FakeWindow(height=PLAYFIELD_ROWS, width=PLAYFIELD_COLS)
        self.screen = GameScreen()
        self.screen._stdscr = self.window
        self.screen._color_pairs = dict(PAIRS)
        patcher = mock.patch.object(screen_module.curses, "doupdate")
        self.doupdate = patcher.start()
        self.addCleanup(patcher.stop)

    def layer_writes(self):
        """The writes above the status line, which every frame also carries."""
        return [write for write in self.window.writes if write[0] != PLAYFIELD_ROWS - 1]

    def test_the_window_is_erased_before_the_frame_is_drawn(self):
        self.screen.render(a_state())

        self.assertEqual(1, self.window.erases)

    def test_the_frame_reaches_the_terminal_in_one_write(self):
        """noutrefresh then doupdate, rather than a refresh per window."""
        self.screen.render(a_state())

        self.assertEqual(1, self.window.refreshes)
        self.assertEqual(1, self.doupdate.call_count)

    def test_a_wall_row_is_drawn_in_the_wall_colour(self):
        self.screen.render(a_state(walls=("╔══╗",)))

        self.assertEqual([(0, 0, "╔══╗", PAIRS[COLOR_WALL])], self.window.writes[:1])

    def test_the_pill_layer_is_drawn_in_its_own_colour(self):
        """The two layers arrive separately so they can be different colours."""
        self.screen.render(a_state(walls=("    ",), pills=("▪▪",)))

        self.assertEqual([(0, 0, "▪▪", PAIRS[COLOR_PILL])], self.layer_writes())

    def test_the_gaps_in_a_layer_are_not_drawn_over_the_layer_beneath(self):
        """A space is a character like any other, so only the runs are written."""
        self.screen.render(a_state(walls=("##  ##",)))

        self.assertEqual(
            [(0, 0, "##", PAIRS[COLOR_WALL]), (0, 4, "##", PAIRS[COLOR_WALL])],
            self.layer_writes(),
        )

    def test_a_blank_row_draws_nothing_at_all(self):
        self.screen.render(a_state(walls=("      ",), pills=("      ",),
                                   status_line=""))

        self.assertEqual([], self.window.writes)

    def test_a_run_at_the_very_end_of_a_row_is_drawn(self):
        self.screen.render(a_state(walls=("   ##",)))

        self.assertEqual([(0, 3, "##", PAIRS[COLOR_WALL])], self.layer_writes())

    def test_a_layer_is_decomposed_once_however_often_it_is_drawn(self):
        """The walls are one tuple for the whole game; runs cost nothing after
        the first frame."""
        state = a_state(walls=("## ##",), pills=("  .  ",))

        with mock.patch.object(screen_module, "_runs_in",
                               wraps=screen_module._runs_in) as runs_in:
            for _ in range(5):
                self.screen.render(state)

        self.assertEqual(2, runs_in.call_count, "one per layer, not per frame")

    def test_a_replaced_layer_is_drawn_again_rather_than_from_the_cache(self):
        """Eating a pill hands render a new tuple, which must not be missed."""
        self.screen.render(a_state(pills=("..",)))
        self.window.writes.clear()

        self.screen.render(a_state(pills=(" .",)))

        self.assertEqual([(0, 1, ".", PAIRS[COLOR_PILL])], self.layer_writes())

    def test_a_sprite_is_drawn_at_its_own_position_and_colour(self):
        self.screen.render(a_state(sprites=(Sprite(4, 7, ("▐█▌",), COLOR_PLAYER),)))

        self.assertIn((4, 7, "▐█▌", PAIRS[COLOR_PLAYER]), self.window.writes)

    def test_a_sprite_is_drawn_over_the_layers_rather_than_under_them(self):
        state = a_state(walls=("##",), sprites=(Sprite(0, 0, ("XX",), COLOR_GHOST),))

        self.screen.render(state)

        self.assertEqual((0, 0, "XX", PAIRS[COLOR_GHOST]), self.window.writes[-2])

    def test_sprites_are_drawn_in_the_order_the_frame_lists_them(self):
        """Which is how the last frame of a capture shows the ghost on top."""
        state = a_state(sprites=(
            Sprite(1, 1, ("G",), COLOR_GHOST),
            Sprite(1, 1, ("P",), COLOR_PLAYER),
        ))

        self.screen.render(state)

        self.assertEqual("P", self.window.text_at(1, 1))

    def test_a_multi_row_sprite_is_drawn_one_row_at_a_time(self):
        self.screen.render(a_state(sprites=(Sprite(2, 3, ("AB", "CD"), COLOR_GHOST),)))

        self.assertIn((2, 3, "AB", PAIRS[COLOR_GHOST]), self.window.writes)
        self.assertIn((3, 3, "CD", PAIRS[COLOR_GHOST]), self.window.writes)

    def test_the_status_line_goes_under_the_playfield(self):
        self.screen.render(a_state(status_line=" score 3"))

        self.assertEqual(
            (PLAYFIELD_ROWS - 1, 0, " score 3", PAIRS[COLOR_STATUS]),
            self.window.writes[-1],
        )

    def test_the_final_cell_of_the_last_row_is_never_written(self):
        """Writing it scrolls the window, which curses treats as an error."""
        line = "X" * PLAYFIELD_COLS

        self.screen.render(a_state(status_line=line))

        self.assertEqual(PLAYFIELD_COLS - 1, len(self.window.writes[-1][2]))

    def test_the_caret_is_parked_out_of_the_way(self):
        self.screen.render(a_state())

        self.assertEqual((PLAYFIELD_ROWS - 1, 0), self.window.cursor)

    def test_a_sprite_off_the_right_edge_keeps_only_what_fits(self):
        self.screen.render(a_state(sprites=(
            Sprite(1, PLAYFIELD_COLS - 2, ("ABCD",), COLOR_PLAYER),
        )))

        self.assertEqual("AB", self.window.text_at(1, PLAYFIELD_COLS - 2))

    def test_a_sprite_past_the_right_edge_is_dropped(self):
        self.screen.render(a_state(sprites=(
            Sprite(1, PLAYFIELD_COLS + 5, ("ABC",), COLOR_PLAYER),
        )))

        self.assertEqual([], [w for w in self.window.writes if w[0] == 1])

    def test_a_sprite_off_the_left_edge_keeps_only_what_fits(self):
        """The mirror of the right edge: trim the overhang, keep the rest."""
        self.screen.render(a_state(sprites=(Sprite(1, -2, ("ABCD",), COLOR_PLAYER),)))

        self.assertEqual("CD", self.window.text_at(1, 0))

    def test_a_sprite_past_the_left_edge_is_dropped(self):
        self.screen.render(a_state(sprites=(Sprite(1, -5, ("ABC",), COLOR_PLAYER),)))

        self.assertEqual([], [w for w in self.window.writes if w[0] == 1])

    def test_a_sprite_below_the_window_is_dropped(self):
        self.screen.render(a_state(sprites=(
            Sprite(PLAYFIELD_ROWS + 3, 0, ("ABC",), COLOR_PLAYER),
        )))

        self.assertEqual([], [w for w in self.window.writes if w[2] == "ABC"])

    def test_a_sprite_above_the_window_is_dropped(self):
        self.screen.render(a_state(sprites=(Sprite(-1, 0, ("ABC",), COLOR_PLAYER),)))

        self.assertEqual([], [w for w in self.window.writes if w[2] == "ABC"])

    def test_a_window_shorter_than_the_playfield_loses_the_rows_that_do_not_fit(self):
        """Curses would raise on every one of them otherwise."""
        self.window.height = 5
        walls = tuple("#" * 4 for _ in range(PLAYFIELD_ROWS))

        self.screen.render(a_state(walls=walls))

        self.assertEqual(set(range(5)), self.window.drawn_rows())

    def test_a_layer_longer_than_the_playfield_stops_at_the_status_line(self):
        walls = tuple("#" * 4 for _ in range(PLAYFIELD_ROWS + 10))

        self.screen.render(a_state(walls=walls))

        self.assertLess(max(self.window.drawn_rows()), PLAYFIELD_ROWS)

    def test_a_frame_arriving_before_the_screen_is_open_is_ignored(self):
        """Frames can arrive from the flow at any time; none of them may raise."""
        closed = GameScreen()

        closed.render(a_state(walls=("###",)))  # no window at all

    def test_an_unknown_colour_slot_falls_back_to_the_default_attribute(self):
        self.screen._color_pairs = {}

        self.screen.render(a_state(walls=("##",)))

        self.assertEqual(screen_module.curses.A_NORMAL, self.window.writes[0][3])


class LifecycleTest(unittest.TestCase):
    """Opening and closing, against a curses that has no terminal behind it."""

    def setUp(self):
        self.window = FakeWindow(height=PLAYFIELD_ROWS, width=PLAYFIELD_COLS)
        self.curses = FakeCurses(window=self.window)
        for patcher in (
            mock.patch.object(screen_module, "curses", self.curses),
            mock.patch.object(screen_module.time, "sleep"),
            mock.patch.object(screen_module.sys, "stdout", io.StringIO()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.screen = GameScreen()

    def test_opening_asks_the_terminal_for_the_size_the_playfield_needs(self):
        self.screen.open()

        self.assertEqual(
            "\033[8;{};{}t".format(PLAYFIELD_ROWS, PLAYFIELD_COLS),
            screen_module.sys.stdout.getvalue(),
        )

    def test_opening_hides_the_caret_and_takes_the_keys_raw(self):
        self.screen.open()

        self.assertIn("noecho", self.curses.calls)
        self.assertIn("cbreak", self.curses.calls)
        self.assertIn("curs_set 0", self.curses.calls)
        self.assertEqual([True], self.window.keypads, "arrow keys would not decode")

    def test_a_terminal_too_small_to_hold_the_playfield_is_refused(self):
        self.window.height, self.window.width = 10, 20

        with self.assertRaises(TerminalTooSmall) as caught:
            self.screen.open()

        message = str(caught.exception)
        self.assertIn("30x40", message)
        self.assertIn("10x20", message)

    def test_a_refused_terminal_is_handed_back_before_the_error_escapes(self):
        """Otherwise the shell is left in raw mode with no caret."""
        self.window.height = 10

        with self.assertRaises(TerminalTooSmall):
            self.screen.open()

        self.assertIn("endwin", self.curses.calls)

    def test_a_terminal_exactly_the_size_of_the_playfield_is_accepted(self):
        self.screen.open()  # 30x40 exactly

        self.assertIn("initscr", self.curses.calls)

    def test_closing_gives_the_terminal_back(self):
        self.screen.open()
        self.screen.close()

        self.assertIn("curs_set 1", self.curses.calls)
        self.assertIn("nocbreak", self.curses.calls)
        self.assertIn("echo", self.curses.calls)
        self.assertIn("endwin", self.curses.calls)

    def test_a_failure_after_taking_the_terminal_hands_it_back(self):
        """Nothing else will: __enter__ never returns, so __exit__ never runs."""
        self.curses.supports_cursor_visibility = False

        with self.assertRaises(screen_module.curses.error):
            self.screen.open()

        self.assertIn("endwin", self.curses.calls)
        self.assertIn("nocbreak", self.curses.calls, "left in cbreak")
        self.assertIn("echo", self.curses.calls, "left with echo off")

    def test_closing_ends_the_window_even_when_the_caret_cannot_be_restored(self):
        """curs_set raises on the terminals close() most has to work on."""
        self.screen.open()
        self.curses.supports_cursor_visibility = False

        self.screen.close()

        self.assertIn("endwin", self.curses.calls)
        self.assertIsNone(self.screen._stdscr, "a closed screen still claims to be open")

    def test_closing_twice_does_nothing_the_second_time(self):
        self.screen.open()
        self.screen.close()
        endwins = self.curses.calls.count("endwin")

        self.screen.close()

        self.assertEqual(endwins, self.curses.calls.count("endwin"))

    def test_closing_a_screen_that_never_opened_is_harmless(self):
        GameScreen().close()

        self.assertEqual([], self.curses.calls)

    def test_the_context_manager_opens_and_closes(self):
        with GameScreen() as screen:
            self.assertIsNotNone(screen._stdscr)

        self.assertIn("endwin", self.curses.calls)

    def test_the_context_manager_tidies_up_but_does_not_swallow_the_error(self):
        with self.assertRaises(ZeroDivisionError):
            with GameScreen():
                raise ZeroDivisionError("something went wrong mid-game")

        self.assertIn("endwin", self.curses.calls)


class ColorTest(unittest.TestCase):
    """The palette, which decides whether the player is visible on the pills."""

    def palette(self, colors=256, supports_default_colors=True):
        window = FakeWindow(height=PLAYFIELD_ROWS, width=PLAYFIELD_COLS)
        fake = FakeCurses(window=window, colors=colors,
                          supports_default_colors=supports_default_colors)
        with mock.patch.object(screen_module, "curses", fake), \
                mock.patch.object(screen_module.time, "sleep"), \
                mock.patch.object(screen_module.sys, "stdout", io.StringIO()):
            screen = GameScreen()
            screen.open()
        return screen, fake

    def test_every_logical_slot_gets_a_colour(self):
        screen, _ = self.palette()

        for slot in (COLOR_WALL, COLOR_PLAYER, COLOR_GHOST, COLOR_STATUS, COLOR_PILL):
            self.assertIn(slot, screen._color_pairs)

    def test_the_terminal_keeps_its_own_background(self):
        _, fake = self.palette()

        self.assertEqual(-1, fake.pairs[COLOR_WALL][1])

    def test_a_terminal_without_a_default_background_falls_back_to_black(self):
        _, fake = self.palette(supports_default_colors=False)

        self.assertEqual(fake.COLOR_BLACK, fake.pairs[COLOR_WALL][1])

    def test_the_player_is_brighter_than_the_pills_it_is_eating(self):
        """Otherwise it disappears into them. Two named shades where there are 256."""
        _, fake = self.palette(colors=256)

        self.assertNotEqual(fake.pairs[COLOR_PILL][0], fake.pairs[COLOR_PLAYER][0])

    def test_on_an_eight_colour_terminal_the_player_is_bold_instead(self):
        """Both are yellow there, so brightness is all that separates them."""
        screen, fake = self.palette(colors=8)

        self.assertEqual(fake.pairs[COLOR_PILL][0], fake.pairs[COLOR_PLAYER][0])
        self.assertTrue(screen._color_pairs[COLOR_PLAYER] & fake.A_BOLD)
        self.assertFalse(screen._color_pairs[COLOR_PILL] & fake.A_BOLD)

    def test_a_terminal_with_no_colour_draws_everything_in_the_default(self):
        screen, _ = self.palette(colors=0)

        self.assertEqual({}, screen._color_pairs)


class AttachTest(unittest.TestCase):
    """Collecting the ViewModel's flow, and letting go of it again."""

    def setUp(self):
        self.window = FakeWindow(height=PLAYFIELD_ROWS, width=PLAYFIELD_COLS)
        self.curses = FakeCurses(window=self.window)
        for patcher in (
            mock.patch.object(screen_module, "curses", self.curses),
            mock.patch.object(screen_module.time, "sleep"),
            mock.patch.object(screen_module.sys, "stdout", io.StringIO()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.screen = GameScreen()
        self.view_model = GameViewModel(seed=1)

    def test_attaching_before_opening_is_refused(self):
        with self.assertRaises(RuntimeError):
            self.screen.attach(self.view_model)

    def test_attaching_paints_the_first_frame_at_once(self):
        """Subscribing replays the current value, so nothing has to ask for it."""
        self.screen.open()

        self.screen.attach(self.view_model)

        self.assertTrue(self.window.writes, "the opening frame never reached the terminal")

    def test_a_later_frame_is_painted_without_being_asked_for(self):
        self.screen.open()
        self.screen.attach(self.view_model)
        self.window.writes.clear()

        self.view_model.tick()

        self.assertTrue(self.window.writes)

    def test_closing_lets_go_of_the_state_flow(self):
        """Closing has to unsubscribe, not merely ignore what arrives.

        A screen that only checked for its window would look the same here --
        until it was opened again, and the subscription nobody let go of
        started painting over the new one. So it is opened again, which is the
        only thing that tells the two apart.
        """
        self.screen.open()
        self.screen.attach(self.view_model)
        self.screen.close()
        self.screen.open()
        self.window.writes.clear()

        self.view_model.tick()

        self.assertEqual([], self.window.writes, "a frame arrived on a flow that was let go")

    def test_a_frame_arriving_while_the_screen_is_shut_paints_nothing(self):
        self.screen.open()
        self.screen.attach(self.view_model)
        self.screen.close()
        self.window.writes.clear()

        self.view_model.tick()

        self.assertEqual([], self.window.writes)

    def test_a_resize_re_measures_and_repaints_from_scratch(self):
        self.screen.open()

        self.screen.handle_resize()

        self.assertIn("update_lines_cols", self.curses.calls)
        self.assertEqual([True], self.window.cleared_ok)

    def test_the_input_timeout_is_passed_to_the_window(self):
        self.screen.open()

        self.screen.set_input_timeout(33)

        self.assertEqual([33], self.window.timeouts)

    def test_a_key_is_read_straight_through(self):
        self.screen.open()
        self.window.keys = [65]

        self.assertEqual(65, self.screen.read_key())

    def test_a_timeout_with_no_key_reads_as_nothing_rather_than_minus_one(self):
        self.screen.open()

        self.assertIsNone(self.screen.read_key())


if __name__ == "__main__":
    unittest.main()
