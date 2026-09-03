"""The game itself: the maze drawn as two layers, and what ticks and keys do to it.

The ViewModel always carves a full-sized maze, so a test cannot hand it a
five-by-five shape of its own. What it can do is seed it, and then read where
things stand out of the frames it publishes -- the sprites say where the player
and the ghost are, and the pill layer says which cells are corridor. That keeps
almost everything here on the published side of the ViewModel rather than
reaching into it.
"""

import unittest

from terminalgame.presentation.maze import Maze
from terminalgame.presentation.state import (
    CELL_COLS,
    CELL_ROWS,
    COLOR_GHOST,
    COLOR_PLAYER,
    PLAYFIELD_COLS,
    Sprite,
)
from terminalgame.presentation.view_model import (
    _GHOST_ART,
    _PILL,
    _PLAYER_ART,
    GameViewModel,
    _odd,
    _to_layers,
    _wall_cell,
)

SEED = 1
STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def sprite_in(state, color):
    """Returns the one sprite of that colour in a frame."""
    return next(sprite for sprite in state.sprites if sprite.color == color)


def cell_of(sprite):
    """Returns the game cell a sprite is standing on.

    Undoes what _build_state does: art is drawn centred on its cell's left
    character, so the middle of the art is the cell's own column.
    """
    middle = sprite.col + len(sprite.art[0]) // 2
    return (sprite.row // CELL_ROWS, middle // CELL_COLS)


def player_cell(state):
    return cell_of(sprite_in(state, COLOR_PLAYER))


def ghost_cell(state):
    return cell_of(sprite_in(state, COLOR_GHOST))


def has_pill(state, row, col):
    """Reports whether that cell still shows a pill in the published layer."""
    return state.pills[row * CELL_ROWS][col * CELL_COLS] == _PILL


def uneaten_directions(state, cell):
    """Returns the steps from a cell onto corridor that still has its pill.

    At the start of a game the only pill missing is the one under the player,
    so this reads as "the ways out" -- without the test having to ask the
    ViewModel for its maze.
    """
    return [step for step in STEPS if has_pill(state, cell[0] + step[0], cell[1] + step[1])]


class OddSizeTest(unittest.TestCase):
    """A maze needs an odd number of cells or its border comes out doubled."""

    def test_an_odd_size_is_left_alone(self):
        self.assertEqual(29, _odd(29))

    def test_an_even_size_loses_its_last_row_or_column(self):
        self.assertEqual(19, _odd(20))

    def test_zero_is_not_made_negative_by_accident(self):
        self.assertEqual(-1, _odd(0), "documenting that _odd is only for real sizes")


class WallGlyphTest(unittest.TestCase):
    """A wall cell picks its line from which of its four neighbours are wall."""

    def glyph(self, rows, row, col):
        return _wall_cell(Maze.from_rows(rows), row, col)

    def test_a_wall_with_no_wall_neighbours_is_a_pillar(self):
        """Nothing to join, so it is a block rather than a length of line."""
        self.assertEqual("■ ", self.glyph((".....",
                                           "..#..",
                                           "....."), 1, 2))

    def test_a_wall_between_two_vertical_walls_carries_the_line_through(self):
        self.assertEqual("║ ", self.glyph((".#.",
                                           ".#.",
                                           ".#."), 1, 1))

    def test_a_wall_between_two_horizontal_walls_carries_the_line_east(self):
        """The right-hand character is the only way a horizontal run joins up."""
        self.assertEqual("══", self.glyph(("...",
                                           "###",
                                           "..."), 1, 1))

    def test_a_single_arm_is_drawn_as_the_through_line(self):
        """There is no half-line in the double-line set to reach for."""
        self.assertEqual("║ ", self.glyph((".#.",
                                           ".#.",
                                           "..."), 1, 1))
        self.assertEqual("═ ", self.glyph(("...",
                                           "##.",
                                           "..."), 1, 1))

    def test_a_corner_joins_the_two_sides_it_has(self):
        corner = ("...",
                  ".##",
                  ".#.")
        self.assertEqual("╔═", self.glyph(corner, 1, 1))

    def test_every_corner_gets_its_own_glyph(self):
        self.assertEqual("╗ ", self.glyph(("...",
                                           "##.",
                                           ".#."), 1, 1))
        self.assertEqual("╚═", self.glyph((".#.",
                                           ".##",
                                           "..."), 1, 1))
        self.assertEqual("╝ ", self.glyph((".#.",
                                           "##.",
                                           "..."), 1, 1))

    def test_three_sides_make_a_tee(self):
        self.assertEqual("╠═", self.glyph((".#.",
                                           ".##",
                                           ".#."), 1, 1))
        self.assertEqual("╣ ", self.glyph((".#.",
                                           "##.",
                                           ".#."), 1, 1))
        self.assertEqual("╦═", self.glyph(("...",
                                           "###",
                                           ".#."), 1, 1))
        self.assertEqual("╩═", self.glyph((".#.",
                                           "###",
                                           "..."), 1, 1))

    def test_four_sides_make_a_cross(self):
        self.assertEqual("╬═", self.glyph((".#.",
                                           "###",
                                           ".#."), 1, 1))

    def test_off_the_grid_counts_as_not_wall_so_the_border_closes(self):
        """A corner of the border must not point an arm off the playfield."""
        self.assertEqual("╔═", self.glyph(("##",
                                           "#."), 0, 0))

    def test_the_line_only_runs_east_when_the_next_cell_is_wall(self):
        """Otherwise the wall would touch the pill in the cell beside it."""
        self.assertEqual(" ", self.glyph(("...",
                                          "##.",
                                          "..."), 1, 1)[1])
        self.assertEqual("═", self.glyph(("...",
                                          ".##",
                                          "..."), 1, 1)[1])


class LayerTest(unittest.TestCase):
    """The two layers a frame carries, each blank where the other has ink."""

    RING = ("#####",
            "#...#",
            "#.#.#",
            "#...#",
            "#####")

    def setUp(self):
        self.walls, self.pills = _to_layers(Maze.from_rows(self.RING))

    def test_each_layer_is_one_line_per_character_row(self):
        self.assertEqual(5 * CELL_ROWS, len(self.walls))
        self.assertEqual(5 * CELL_ROWS, len(self.pills))

    def test_each_line_is_one_cell_width_per_column(self):
        for line in self.walls + self.pills:
            self.assertEqual(5 * CELL_COLS, len(line))

    def test_the_border_is_drawn_as_a_closed_rectangle(self):
        self.assertEqual("╔═══════╗ ", self.walls[0])
        self.assertEqual("╚═══════╝ ", self.walls[4])

    def test_an_island_is_drawn_as_a_pillar(self):
        self.assertEqual("■", self.walls[2][2 * CELL_COLS])

    def test_every_corridor_cell_carries_exactly_one_pill(self):
        """One pill marks one place a sprite can stand -- two would say there were two."""
        maze = Maze.from_rows(self.RING)

        self.assertEqual(len(maze.open_cells()), sum(line.count(_PILL) for line in self.pills))

    def test_the_pill_sits_on_the_cell_centre_line(self):
        """The left character, which is where a wall's line sits too."""
        self.assertEqual(_PILL, self.pills[1][1 * CELL_COLS])
        self.assertEqual(" ", self.pills[1][1 * CELL_COLS + 1])

    def test_a_wall_cell_carries_no_pill(self):
        """Which is why the islands braiding leaves behind are blank inside."""
        self.assertEqual("  ", self.pills[2][2 * CELL_COLS:2 * CELL_COLS + CELL_COLS])

    def test_neither_layer_ever_draws_over_the_other(self):
        for wall_line, pill_line in zip(self.walls, self.pills):
            for wall_char, pill_char in zip(wall_line, pill_line):
                self.assertTrue(
                    wall_char == " " or pill_char == " ",
                    "both layers have ink at the same character",
                )


class SpriteArtTest(unittest.TestCase):
    """Art has to be an odd width to sit centred on the corridor's centre line."""

    def test_both_sprites_are_a_cell_tall(self):
        self.assertEqual(CELL_ROWS, len(_PLAYER_ART))
        self.assertEqual(CELL_ROWS, len(_GHOST_ART))

    def test_both_sprites_are_an_odd_number_of_characters_wide(self):
        self.assertEqual(1, len(_PLAYER_ART[0]) % 2)
        self.assertEqual(1, len(_GHOST_ART[0]) % 2)

    def test_the_two_are_told_apart_by_shape_as_well_as_by_colour(self):
        self.assertNotEqual(_PLAYER_ART, _GHOST_ART)


class NewGameTest(unittest.TestCase):

    def setUp(self):
        self.view_model = GameViewModel(seed=SEED)
        self.state = self.view_model.state.value

    def test_the_opening_frame_is_at_tick_zero(self):
        self.assertEqual(0, self.state.tick)

    def test_the_opening_score_is_zero(self):
        self.assertIn("score 0", self.state.status_line)

    def test_the_status_line_says_which_keys_do_something(self):
        self.assertIn("arrows", self.state.status_line)
        self.assertIn("q quits", self.state.status_line)

    def test_the_status_line_fits_the_playfield(self):
        """The last cell belongs to curses, so the budget is one short."""
        self.assertLessEqual(len(self.state.status_line), PLAYFIELD_COLS - 1)

    def test_the_frame_carries_a_player_and_a_ghost(self):
        self.assertEqual(2, len(self.state.sprites))
        self.assertEqual(_PLAYER_ART, sprite_in(self.state, COLOR_PLAYER).art)
        self.assertEqual(_GHOST_ART, sprite_in(self.state, COLOR_GHOST).art)

    def test_the_two_do_not_start_on_the_same_cell(self):
        self.assertNotEqual(player_cell(self.state), ghost_cell(self.state))

    def test_both_start_somewhere_they_could_have_walked_to(self):
        """Neither can start inside a wall, whatever shape the maze took."""
        for seed in range(10):
            state = GameViewModel(seed=seed).state.value
            ghost = ghost_cell(state)

            self.assertTrue(
                has_pill(state, *ghost),
                "seed {} started the ghost off the corridor".format(seed),
            )
            self.assertTrue(uneaten_directions(state, player_cell(state)))

    def test_the_pill_under_the_player_is_taken_without_being_scored(self):
        """Otherwise the game opens at 1, waiting on a pill nobody can see."""
        self.assertFalse(has_pill(self.state, *player_cell(self.state)))
        self.assertIn("score 0", self.state.status_line)

    def test_the_same_seed_gives_the_same_game(self):
        self.assertEqual(GameViewModel(seed=SEED).state.value, self.state)

    def test_a_different_seed_gives_a_different_game(self):
        self.assertNotEqual(GameViewModel(seed=SEED + 1).state.value, self.state)

    def test_the_player_is_drawn_over_the_ghost(self):
        """Sprites are drawn in order, so the player being last keeps it visible."""
        self.assertEqual(COLOR_PLAYER, self.state.sprites[-1].color)


class PlayerMovementTest(unittest.TestCase):

    def setUp(self):
        self.view_model = GameViewModel(seed=SEED)
        self.frames = []
        self.view_model.state.subscribe(self.frames.append)
        self.start = player_cell(self.frames[-1])
        self.open_step = uneaten_directions(self.frames[-1], self.start)[0]
        self.blocked_step = next(
            step for step in STEPS
            if not has_pill(self.frames[-1], self.start[0] + step[0], self.start[1] + step[1])
        )

    def test_an_arrow_key_moves_the_player_one_whole_cell(self):
        self.view_model.on_direction(*self.open_step)

        self.assertEqual(
            (self.start[0] + self.open_step[0], self.start[1] + self.open_step[1]),
            player_cell(self.view_model.state.value),
        )

    def test_moving_publishes_a_new_frame(self):
        before = len(self.frames)

        self.view_model.on_direction(*self.open_step)

        self.assertEqual(before + 1, len(self.frames))

    def test_the_pill_moved_onto_is_eaten_and_scored(self):
        landing = (self.start[0] + self.open_step[0], self.start[1] + self.open_step[1])

        self.view_model.on_direction(*self.open_step)
        state = self.view_model.state.value

        self.assertFalse(has_pill(state, *landing), "the pill survived being walked on")
        self.assertIn("score 1", state.status_line)

    def test_eating_a_pill_republishes_the_layer_rather_than_editing_it(self):
        """The published layer is a tuple and has to stay one."""
        before = self.view_model.state.value.pills

        self.view_model.on_direction(*self.open_step)

        self.assertIsNot(before, self.view_model.state.value.pills)

    def test_walking_back_over_an_eaten_cell_scores_nothing(self):
        back = (-self.open_step[0], -self.open_step[1])

        self.view_model.on_direction(*self.open_step)
        self.view_model.on_direction(*back)

        self.assertIn("score 1", self.view_model.state.value.status_line)

    def test_a_press_into_a_wall_leaves_the_player_where_it_was(self):
        self.view_model.on_direction(*self.blocked_step)

        self.assertEqual(self.start, player_cell(self.view_model.state.value))

    def test_a_press_into_a_wall_publishes_nothing_at_all(self):
        """An identical frame costs the terminal nothing, so none is offered."""
        before = len(self.frames)

        self.view_model.on_direction(*self.blocked_step)

        self.assertEqual(before, len(self.frames))

    def test_the_maze_layers_are_the_same_objects_from_frame_to_frame(self):
        """The walls never change, so they are never rebuilt."""
        before = self.view_model.state.value.walls

        self.view_model.on_direction(*self.open_step)

        self.assertIs(before, self.view_model.state.value.walls)


class GhostMovementTest(unittest.TestCase):

    def setUp(self):
        self.view_model = GameViewModel(seed=SEED)
        self.frames = []
        self.view_model.state.subscribe(self.frames.append)

    def test_a_tick_advances_the_tick_count(self):
        self.view_model.tick()

        self.assertEqual(1, self.view_model.state.value.tick)

    def test_a_tick_publishes_a_frame(self):
        before = len(self.frames)

        self.view_model.tick()

        self.assertEqual(before + 1, len(self.frames))

    def test_a_tick_moves_the_ghost_exactly_one_cell(self):
        before = ghost_cell(self.view_model.state.value)

        self.view_model.tick()
        after = ghost_cell(self.view_model.state.value)

        distance = abs(after[0] - before[0]) + abs(after[1] - before[1])
        self.assertEqual(1, distance, "the ghost teleported from {} to {}".format(before, after))

    def test_a_tick_does_not_move_the_player(self):
        before = player_cell(self.view_model.state.value)

        self.view_model.tick()

        self.assertEqual(before, player_cell(self.view_model.state.value))

    def test_the_ghost_never_walks_into_a_wall(self):
        """Checked against the wall layer, which is the maze as it is drawn."""
        for seed in range(5):
            view_model = GameViewModel(seed=seed)
            walls = view_model.state.value.walls

            for _ in range(200):
                view_model.tick()
                row, col = ghost_cell(view_model.state.value)

                self.assertEqual(
                    " ", walls[row * CELL_ROWS][col * CELL_COLS],
                    "seed {} put the ghost inside a wall at {}".format(seed, (row, col)),
                )

    def test_the_ghost_carries_straight_on_where_it_can(self):
        """No dead ends means it rarely has to turn, and never has to reverse."""
        view_model = GameViewModel(seed=SEED)
        positions = [ghost_cell(view_model.state.value)]
        for _ in range(30):
            view_model.tick()
            positions.append(ghost_cell(view_model.state.value))

        steps = [
            (b[0] - a[0], b[1] - a[1])
            for a, b in zip(positions, positions[1:])
        ]
        reversals = sum(
            1 for a, b in zip(steps, steps[1:]) if b == (-a[0], -a[1])
        )
        self.assertLess(reversals, len(steps) // 3, "the ghost spent its time doubling back")


class EndingTest(unittest.TestCase):
    """The two ways a game ends, and what stops once one of them has.

    Both endings need the pieces put somewhere a fair game would take hundreds
    of moves to reach, so these reach past the published frames and place them
    directly. Everything asserted afterwards is still read off the frames.
    """

    def setUp(self):
        self.view_model = GameViewModel(seed=SEED)
        self.frames = []
        self.view_model.state.subscribe(self.frames.append)
        self.start = player_cell(self.frames[-1])
        self.step = uneaten_directions(self.frames[-1], self.start)[0]
        self.landing = (self.start[0] + self.step[0], self.start[1] + self.step[1])

    def put_ghost_on(self, cell, step=(0, 0)):
        """Stands the ghost on a cell, facing a given way."""
        self.view_model._ghost_row, self.view_model._ghost_col = cell
        self.view_model._ghost_step = step

    def test_the_ghost_walking_onto_the_player_ends_the_game(self):
        self.put_ghost_on(self.landing, step=(-self.step[0], -self.step[1]))

        self.view_model.tick()

        self.assertIn("CAUGHT", self.view_model.state.value.status_line)

    def test_the_player_walking_onto_the_ghost_ends_the_game_too(self):
        self.put_ghost_on(self.landing)

        self.view_model.on_direction(*self.step)

        self.assertIn("CAUGHT", self.view_model.state.value.status_line)

    def test_a_capture_draws_the_ghost_on_top_of_the_player(self):
        """Otherwise the last frame looks like any other."""
        self.put_ghost_on(self.landing)

        self.view_model.on_direction(*self.step)

        self.assertEqual(COLOR_GHOST, self.view_model.state.value.sprites[-1].color)

    def test_a_capture_keeps_the_score_that_was_earned(self):
        self.put_ghost_on(self.landing)

        self.view_model.on_direction(*self.step)

        self.assertIn("score 1", self.view_model.state.value.status_line)

    def test_eating_the_last_pill_ends_the_game(self):
        self.view_model._pills_left = 1

        self.view_model.on_direction(*self.step)

        self.assertIn("CLEARED", self.view_model.state.value.status_line)

    def test_the_two_endings_are_told_apart_by_name(self):
        cleared = GameViewModel(seed=SEED)
        cleared._pills_left = 1
        cleared.on_direction(*self.step)

        self.assertNotIn("CAUGHT", cleared.state.value.status_line)
        self.assertIn("CLEARED", cleared.state.value.status_line)

    def test_walking_into_the_ghost_for_the_last_pill_is_still_a_capture(self):
        """The capture is checked first: they still walked into the ghost."""
        self.view_model._pills_left = 1
        self.put_ghost_on(self.landing)

        self.view_model.on_direction(*self.step)

        self.assertIn("CAUGHT", self.view_model.state.value.status_line)
        self.assertNotIn("CLEARED", self.view_model.state.value.status_line)

    def test_a_finished_game_stops_ticking(self):
        self.put_ghost_on(self.landing)
        self.view_model.on_direction(*self.step)
        final = self.view_model.state.value

        for _ in range(5):
            self.view_model.tick()

        self.assertEqual(final.tick, self.view_model.state.value.tick)
        self.assertEqual(final, self.view_model.state.value)

    def test_a_finished_game_publishes_nothing_more(self):
        self.put_ghost_on(self.landing)
        self.view_model.on_direction(*self.step)
        published = len(self.frames)

        self.view_model.tick()
        self.view_model.on_direction(*self.step)

        self.assertEqual(published, len(self.frames))

    def test_a_finished_game_ignores_the_arrow_keys(self):
        self.view_model._pills_left = 1
        self.view_model.on_direction(*self.step)
        resting = player_cell(self.view_model.state.value)

        for step in STEPS:
            self.view_model.on_direction(*step)

        self.assertEqual(resting, player_cell(self.view_model.state.value))


if __name__ == "__main__":
    unittest.main()
