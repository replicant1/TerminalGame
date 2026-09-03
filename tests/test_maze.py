"""Maze: the grid itself, the questions asked of it, and what generation promises."""

import unittest

from terminalgame.presentation.maze import Maze

# A ring of corridor around a single wall cell. Small enough to reason about by
# hand, and it has one of everything: a border, an island, and a loop.
RING = (
    "#####",
    "#...#",
    "#.#.#",
    "#...#",
    "#####",
)


class MazeShapeTest(unittest.TestCase):

    def test_from_rows_reads_the_shape_it_is_given(self):
        maze = Maze.from_rows(RING)

        self.assertEqual(5, maze.rows)
        self.assertEqual(5, maze.cols)
        self.assertTrue(maze.is_open(1, 1))
        self.assertFalse(maze.is_open(2, 2), "the island came out open")
        self.assertFalse(maze.is_open(0, 0))

    def test_from_rows_takes_a_different_corridor_character(self):
        maze = Maze.from_rows(("XX", "X."), open_char="X")

        self.assertTrue(maze.is_open(0, 0))
        self.assertFalse(maze.is_open(1, 1), "the default corridor character still counted")

    def test_out_of_bounds_counts_as_wall(self):
        """Everything that walks the grid leans on this instead of guarding."""
        maze = Maze.from_rows(RING)

        self.assertFalse(maze.is_open(-1, 1))
        self.assertFalse(maze.is_open(1, -1))
        self.assertFalse(maze.is_open(5, 1))
        self.assertFalse(maze.is_open(1, 5))

    def test_an_empty_grid_is_refused(self):
        with self.assertRaises(ValueError):
            Maze([])
        with self.assertRaises(ValueError):
            Maze([[]])

    def test_a_ragged_grid_is_refused(self):
        with self.assertRaises(ValueError):
            Maze([[True, True], [True]])

    def test_the_grid_is_copied_rather_than_kept(self):
        grid = [[True, True], [True, True]]
        maze = Maze(grid)

        grid[0][0] = False

        self.assertTrue(maze.is_open(0, 0), "an edit to the caller's grid reached the maze")

    def test_to_rows_draws_what_it_was_built_from(self):
        self.assertEqual(RING, Maze.from_rows(RING).to_rows())

    def test_to_rows_takes_the_characters_it_is_given(self):
        self.assertEqual(
            ("@@", "@ "),
            Maze.from_rows(("##", "#.")).to_rows(wall="@", corridor=" "),
        )

    def test_repr_says_the_size_and_how_much_is_corridor(self):
        self.assertEqual("Maze(5x5, 8 open cells)", repr(Maze.from_rows(RING)))


class MazeQueryTest(unittest.TestCase):

    def setUp(self):
        self.maze = Maze.from_rows(RING)

    def test_open_cells_come_back_in_row_major_order(self):
        self.assertEqual(
            ((1, 1), (1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 2), (3, 3)),
            self.maze.open_cells(),
        )

    def test_wall_cells_are_the_rest(self):
        walls = self.maze.wall_cells()

        self.assertEqual(25 - 8, len(walls))
        self.assertIn((2, 2), walls)
        self.assertNotIn((1, 1), walls)

    def test_neighbours_are_the_four_sides_that_are_on_the_grid(self):
        self.assertEqual(((1, 2), (3, 2), (2, 1), (2, 3)), self.maze.neighbours(2, 2))

    def test_neighbours_are_clipped_at_a_corner(self):
        self.assertEqual(((1, 0), (0, 1)), self.maze.neighbours(0, 0))

    def test_open_neighbours_are_the_ways_out(self):
        self.assertEqual(((1, 2), (3, 2), (2, 1), (2, 3)), self.maze.open_neighbours(2, 2))
        self.assertEqual(((2, 1), (1, 2)), self.maze.open_neighbours(1, 1))

    def test_reachable_from_finds_the_whole_loop(self):
        self.assertEqual(set(self.maze.open_cells()), set(self.maze.reachable_from(1, 1)))

    def test_reachable_from_includes_where_it_started(self):
        self.assertIn((1, 1), self.maze.reachable_from(1, 1))

    def test_nothing_is_reachable_from_inside_a_wall(self):
        self.assertEqual(frozenset(), self.maze.reachable_from(2, 2))

    def test_reachable_from_stops_at_the_edge_of_its_own_region(self):
        maze = Maze.from_rows(("#####",
                               "#.#.#",
                               "#####"))

        self.assertEqual(frozenset({(1, 1)}), maze.reachable_from(1, 1))

    def test_a_ring_is_fully_connected(self):
        self.assertTrue(self.maze.is_fully_connected())

    def test_two_separated_corridors_are_not_fully_connected(self):
        maze = Maze.from_rows(("#####",
                               "#.#.#",
                               "#####"))

        self.assertFalse(maze.is_fully_connected())

    def test_a_maze_with_no_corridor_counts_as_connected(self):
        self.assertTrue(Maze.from_rows(("##", "##")).is_fully_connected())

    def test_a_ring_has_no_dead_ends(self):
        self.assertEqual((), self.maze.dead_ends())

    def test_a_dead_end_is_reported_by_position(self):
        """Both ends of an unbraided corridor have one way out, so both are named."""
        maze = Maze.from_rows(("#####",
                               "#...#",
                               "###.#",
                               "#####"))

        self.assertEqual(((1, 1), (2, 3)), maze.dead_ends())

    def test_a_lone_cell_is_a_dead_end_with_no_ways_out_at_all(self):
        maze = Maze.from_rows(("###",
                               "#.#",
                               "###"))

        self.assertEqual(((1, 1),), maze.dead_ends())

    def test_a_wall_block_away_from_the_border_is_an_island(self):
        self.assertEqual((frozenset({(2, 2)}),), self.maze.islands())

    def test_the_border_is_not_an_island(self):
        """It is all one region, and it touches the edge, so it is not counted."""
        maze = Maze.from_rows(("###",
                               "#.#",
                               "###"))

        self.assertEqual((), maze.islands())

    def test_islands_are_whole_regions_rather_than_single_cells(self):
        maze = Maze.from_rows(("######",
                               "#....#",
                               "#.##.#",
                               "#....#",
                               "######"))

        self.assertEqual((frozenset({(2, 2), (2, 3)}),), maze.islands())

    def test_two_islands_are_reported_separately(self):
        maze = Maze.from_rows(("#######",
                               "#.....#",
                               "#.#.#.#",
                               "#.....#",
                               "#######"))

        self.assertEqual(
            {frozenset({(2, 2)}), frozenset({(2, 4)})},
            set(maze.islands()),
        )


class MazePlacementTest(unittest.TestCase):

    def setUp(self):
        self.maze = Maze.from_rows(RING)

    def test_nearest_open_to_a_wall_is_the_corridor_beside_it(self):
        """The island's centre is wall, so something wanting it stands next to it."""
        self.assertIn(self.maze.nearest_open(2, 2), ((1, 2), (2, 1), (2, 3), (3, 2)))

    def test_nearest_open_to_a_corridor_cell_is_that_cell(self):
        self.assertEqual((1, 1), self.maze.nearest_open(1, 1))

    def test_nearest_open_to_a_spot_outside_the_maze_is_the_closest_corner(self):
        self.assertEqual((1, 1), self.maze.nearest_open(-4, -4))

    def test_farthest_open_is_the_far_corner(self):
        self.assertEqual((3, 3), self.maze.farthest_open(1, 1))

    def test_the_pair_never_place_two_things_on_one_cell(self):
        """What keeps the player and the ghost from starting on top of each other."""
        for seed in range(20):
            maze = Maze.generate(11, 11, seed=seed)
            player = maze.nearest_open(5, 5)
            ghost = maze.farthest_open(*player)

            self.assertNotEqual(player, ghost, "seed {} started them together".format(seed))


class MazeGenerationTest(unittest.TestCase):
    """What generation promises, checked over a spread of seeds and sizes."""

    SIZES = ((5, 5), (9, 9), (11, 21), (29, 19), (5, 7))

    def test_a_seed_gives_the_same_maze_twice(self):
        self.assertEqual(
            Maze.generate(15, 15, seed=42).to_rows(),
            Maze.generate(15, 15, seed=42).to_rows(),
        )

    def test_different_seeds_give_different_mazes(self):
        shapes = {Maze.generate(15, 15, seed=seed).to_rows() for seed in range(8)}

        self.assertGreater(len(shapes), 1, "the seed made no difference")

    def test_the_maze_is_the_size_it_was_asked_for(self):
        for rows, cols in self.SIZES:
            maze = Maze.generate(rows, cols, seed=1)

            self.assertEqual((rows, cols), (maze.rows, maze.cols))

    def test_braiding_leaves_no_dead_ends(self):
        for rows, cols in self.SIZES:
            for seed in range(8):
                maze = Maze.generate(rows, cols, seed=seed)

                self.assertEqual(
                    (), maze.dead_ends(),
                    "{}x{} seed {} left dead ends:\n{}".format(
                        rows, cols, seed, "\n".join(maze.to_rows())
                    ),
                )

    def test_every_corridor_can_be_walked_to_from_every_other(self):
        """Otherwise pills would be stranded and the arena could not be cleared."""
        for rows, cols in self.SIZES:
            for seed in range(8):
                maze = Maze.generate(rows, cols, seed=seed)

                self.assertTrue(
                    maze.is_fully_connected(),
                    "{}x{} seed {} came out in pieces:\n{}".format(
                        rows, cols, seed, "\n".join(maze.to_rows())
                    ),
                )

    def test_the_outermost_cells_are_always_wall(self):
        for seed in range(8):
            maze = Maze.generate(11, 21, seed=seed)
            border = (
                [(0, col) for col in range(maze.cols)]
                + [(maze.rows - 1, col) for col in range(maze.cols)]
                + [(row, 0) for row in range(maze.rows)]
                + [(row, maze.cols - 1) for row in range(maze.rows)]
            )

            for row, col in border:
                self.assertFalse(
                    maze.is_open(row, col),
                    "seed {} left a hole in the border at {}".format(seed, (row, col)),
                )

    def test_braiding_leaves_islands_for_the_corridors_to_run_around(self):
        """A perfect maze is all one wall region; loops are what cut islands out."""
        maze = Maze.generate(11, 21, seed=3)

        self.assertTrue(maze.islands(), "no island survived braiding")

    def test_something_was_actually_carved(self):
        maze = Maze.generate(11, 11, seed=0)

        self.assertGreater(len(maze.open_cells()), 10)

    def test_a_maze_too_small_to_braid_is_refused(self):
        """One junction row means a corridor end with one way out and no second."""
        for rows, cols in ((2, 9), (9, 2), (1, 1), (0, 5),
                           (3, 3), (3, 9), (9, 3), (4, 9), (9, 4)):
            with self.assertRaises(ValueError):
                Maze.generate(rows, cols)

    def test_the_smallest_maze_that_can_be_braided_is_allowed(self):
        maze = Maze.generate(5, 5, seed=0)

        self.assertEqual((), maze.dead_ends())
        self.assertTrue(maze.is_fully_connected())


if __name__ == "__main__":
    unittest.main()
