"""How a ghost chooses its next step, and the seam that lets it be swapped.

Everything here works on hand-built mazes of a few cells, which is the point
of the strategy being its own abstraction: deciding where to go is now a pure
question about a maze, a position and a heading, and needs neither a game nor
a terminal to ask.
"""

import random
import unittest
from dataclasses import FrozenInstanceError

from terminalgame.presentation.ghost import (
    STEPS,
    GhostStrategy,
    Surroundings,
    Wanderer,
    open_steps,
)
from terminalgame.presentation.maze import Maze

# A straight length of corridor: (1, 1) through (1, 3), walled all round.
CORRIDOR = (
    "#####",
    "#...#",
    "#####",
)

# A ring of corridor around a single wall cell. Every open cell has two ways
# out, so a ghost in here always has somewhere to turn rather than reverse.
RING = (
    "#####",
    "#...#",
    "#.#.#",
    "#...#",
    "#####",
)

# A corridor running east that stops, with one way on to the south. A ghost
# arriving at (1, 2) has its heading blocked and the way it came still open,
# which is the only shape where refusing to double back makes any difference.
ELBOW = (
    "#####",
    "#..##",
    "##.##",
    "#####",
)

# The one shape a braided maze never contains: (1, 2) has a single way out,
# which is the way in. A ghost arriving there has nothing to do but reverse.
DEAD_END = (
    "####",
    "#..#",
    "#.##",
    "####",
)


def surroundings(rows, position, heading, player=(1, 1)):
    """Builds what a strategy is handed, out of lines of text.

    Args:
        rows: The maze, as `Maze._from_rows` reads it.
        position: The cell the ghost is standing on.
        heading: The step it took to get there.
        player: Where the player is, which only a hunting strategy reads.

    Returns:
        A Surroundings over that maze.
    """
    return Surroundings(
        maze=Maze._from_rows(rows),
        position=position,
        heading=heading,
        player=player,
    )


class PicksTheNth:
    """A stand-in for random.Random that always chooses the same index.

    Records what it was offered as well as answering, because half of what the
    Wanderer decides is which turns it puts up for choosing at all -- and a
    strategy that offered the way it came would be wrong even on the ticks
    where the coin happened to land elsewhere.
    """

    def __init__(self, index=0):
        self._index = index
        self.offered = []

    def choice(self, sequence):
        self.offered.append(tuple(sequence))
        return sequence[self._index]


class WandererTest(unittest.TestCase):
    """The ghost the game ships with: straight on, then a turn at random."""

    def test_it_carries_straight_on_where_the_cell_ahead_is_open(self):
        wanderer = Wanderer(PicksTheNth())

        step = wanderer.next_step(surroundings(CORRIDOR, (1, 1), (0, 1)))

        self.assertEqual((0, 1), step)

    def test_carrying_straight_on_costs_no_randomness(self):
        """Otherwise every seeded game would burn a number a tick doing nothing."""
        rng = PicksTheNth()
        wanderer = Wanderer(rng)

        wanderer.next_step(surroundings(CORRIDOR, (1, 1), (0, 1)))

        self.assertEqual([], rng.offered)

    def test_it_turns_where_the_cell_ahead_is_wall(self):
        wanderer = Wanderer(PicksTheNth())

        step = wanderer.next_step(surroundings(ELBOW, (1, 2), (0, 1)))

        self.assertEqual((1, 0), step, "it walked into the end of the corridor")

    def test_every_turn_but_the_way_it_came_is_offered(self):
        """The way back is open here, which is what makes the exclusion visible."""
        rng = PicksTheNth()
        wanderer = Wanderer(rng)

        wanderer.next_step(surroundings(ELBOW, (1, 2), (0, 1)))

        self.assertEqual([((1, 0),)], rng.offered, "it was offered the way it came")

    def test_it_reverses_only_where_there_is_nothing_else(self):
        rng = PicksTheNth()
        wanderer = Wanderer(rng)

        step = wanderer.next_step(surroundings(DEAD_END, (1, 2), (0, 1)))

        self.assertEqual((0, -1), step)
        self.assertEqual([], rng.offered, "reversing is not a choice, so nothing was chosen")

    def test_a_heading_pointing_at_a_wall_is_coped_with(self):
        """The first tick of a game has a heading the ghost never actually took."""
        wanderer = Wanderer(PicksTheNth())

        step = wanderer.next_step(surroundings(CORRIDOR, (1, 1), (-1, 0)))

        self.assertEqual((0, 1), step)

    def test_it_never_returns_a_step_into_a_wall(self):
        maze = Maze._from_rows(RING)
        wanderer = Wanderer(random.Random(1))
        position, heading = (1, 1), (0, 1)

        for _ in range(200):
            heading = wanderer.next_step(
                Surroundings(maze=maze, position=position, heading=heading, player=(1, 1))
            )
            position = (position[0] + heading[0], position[1] + heading[1])

            self.assertTrue(
                maze.is_open(*position),
                "the wanderer stepped onto {}".format(position),
            )

    def test_the_same_seed_gives_the_same_turns(self):
        """A seeded wanderer is what makes a whole seeded game reproducible."""
        junction = surroundings(RING, (1, 2), (1, 0))

        first = [Wanderer(random.Random(3)).next_step(junction) for _ in range(20)]
        second = [Wanderer(random.Random(3)).next_step(junction) for _ in range(20)]

        self.assertEqual(first, second)

    def test_it_brings_its_own_randomness_when_given_none(self):
        step = Wanderer().next_step(surroundings(RING, (1, 2), (1, 0)))

        self.assertIn(step, ((0, -1), (0, 1)))


class OpenStepsHelperTest(unittest.TestCase):
    """The shared "where may I go from here" every strategy starts with."""

    def test_it_offers_the_open_steps_in_a_fixed_order(self):
        """Fixed, so two strategies do not break ties differently by accident."""
        steps = open_steps(surroundings(RING, (1, 2), (0, 1)))

        self.assertEqual(((0, -1), (0, 1)), steps)

    def test_a_wall_is_not_offered(self):
        steps = open_steps(surroundings(RING, (1, 2), (0, 1)))

        self.assertNotIn((1, 0), steps, "the island was offered as a way on")

    def test_off_the_board_is_not_offered(self):
        """The border closes the maze, so nothing here needs its own guard."""
        steps = open_steps(surroundings(CORRIDOR, (1, 1), (0, 1)))

        self.assertEqual(((0, 1),), steps)

    def test_an_excluded_step_is_dropped_even_though_it_is_open(self):
        steps = open_steps(surroundings(RING, (1, 2), (0, 1)), exclude=((0, -1),))

        self.assertEqual(((0, 1),), steps)


class SurroundingsTest(unittest.TestCase):

    def test_it_cannot_be_edited_by_the_strategy_it_is_handed_to(self):
        """Returning a step is the only move a strategy has."""
        given = surroundings(RING, (1, 2), (0, 1))

        with self.assertRaises(FrozenInstanceError):
            given.position = (1, 1)


class GhostStrategyTest(unittest.TestCase):

    def test_a_strategy_that_does_not_choose_a_step_cannot_be_built(self):
        class Undecided(GhostStrategy):
            pass

        with self.assertRaises(TypeError):
            Undecided()

    def test_the_four_steps_are_the_ones_the_grid_allows(self):
        """One cell, never diagonal, so exactly one component is non-zero."""
        self.assertEqual(4, len(STEPS))
        for step in STEPS:
            self.assertEqual(1, sum(1 for part in step if part != 0))
            self.assertIn(sum(abs(part) for part in step), (1,))


if __name__ == "__main__":
    unittest.main()
