"""How a ghost decides where to go next.

The decision is separated from the ghost itself. `GameViewModel` owns where
the ghost stands and does the moving; a `GhostStrategy` owns nothing and only
answers one question -- given the maze, where you are and which way you are
facing, which way now? That split is what lets a different ghost be dropped
into a game without the rules of the game changing around it: the ViewModel
takes one as a constructor argument and never learns which kind it got.

A strategy is handed a `Surroundings` rather than a list of arguments, because
the useful strategies do not all need the same things. `Wanderer` below reads
only the maze and its own heading, while a ghost that hunts needs the player's
cell as well -- and a later one that keeps out of another ghost's way would
need something neither of them asks for. Growing the value object leaves every
existing strategy compiling and running unchanged, which adding a fifth
positional parameter would not.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .maze import Cell, Maze

# A single move, as (rows, columns). Always one cell, never diagonal, so each
# component is -1, 0 or 1 and exactly one of them is non-zero.
Step = Tuple[int, int]

# North, south, west, east -- every step a ghost may take. Public because a
# strategy written elsewhere needs the same four and should not have to
# rewrite them in a different order and get subtly different tie-breaking.
STEPS: Tuple[Step, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


@dataclass(frozen=True)
class Surroundings:
    """What a strategy is told before it chooses a step.

    Frozen, so a strategy cannot move the ghost by editing what it was handed:
    the only thing it may do is return a step and let the ViewModel apply it.

    Attributes:
        maze: The maze being played, for asking which cells are open.
        position: The cell the ghost is standing on, in cells rather than
            characters -- a strategy never sees the screen.
        heading: The step the ghost took to arrive, which is what "carry
            straight on" means. The first tick of a game has a heading the
            ghost never actually took, so a strategy must cope with it
            pointing at a wall.
        player: The cell the player is standing on, for a strategy that hunts.
    """

    maze: Maze
    position: Cell
    heading: Step
    player: Cell


class GhostStrategy(ABC):
    """Chooses which way a ghost goes next. Owns no state of the game's."""

    @abstractmethod
    def next_step(self, surroundings: Surroundings) -> Step:
        """Chooses the ghost's next move.

        Called once per tick, before anything else has moved.

        Args:
            surroundings: Where the ghost is, which way it is facing, and the
                maze and player to reason about.

        Returns:
            One of `STEPS`. It should land on an open cell: a step into a wall
            is refused by the caller and the ghost stands still for that tick,
            which is a strategy quietly doing nothing rather than a ghost
            inside a wall.
        """


def open_steps(
    surroundings: Surroundings, exclude: Sequence[Step] = ()
) -> Tuple[Step, ...]:
    """Returns the steps from here that land on corridor.

    Shared by strategies rather than kept private to one, since every strategy
    has to start by working out where it may legally go.

    Args:
        surroundings: The ghost's position and the maze to look in.
        exclude: Steps to leave out whether they are open or not, which is how
            a strategy refuses to double back.

    Returns:
        The open steps, in `STEPS` order.
    """
    row, col = surroundings.position
    return tuple(
        step
        for step in STEPS
        if step not in exclude
        and surroundings.maze.is_open(row + step[0], col + step[1])
    )


class Wanderer(GhostStrategy):
    """Carries straight on where it can, turns at random where it cannot.

    The ghost the game ships with. It does not hunt: it holds its heading
    until the corridor runs out, then picks among the ways on that are not the
    way it came. Because the maze is braided and so has no dead ends, a ghost
    that has just arrived somewhere always has such a way on, and reversing is
    a last resort rather than the usual outcome.
    """

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        """Prepares a wandering ghost.

        Args:
            rng: Source of randomness for the turns. Seeding it is what makes
                a game reproducible, and so what lets a test assert anything
                about one. None gives different turns every run.
        """
        self._rng = rng if rng is not None else random.Random()

    def next_step(self, surroundings: Surroundings) -> Step:
        """Carries on ahead, or turns.

        Args:
            surroundings: Where the ghost is and which way it is facing.

        Returns:
            The heading unchanged where the cell ahead is open, otherwise a
            turn chosen at random, and the way back only when there is
            nothing else at all.
        """
        row, col = surroundings.position
        d_row, d_col = surroundings.heading
        if surroundings.maze.is_open(row + d_row, col + d_col):
            return surroundings.heading

        back = (-d_row, -d_col)
        turns = open_steps(surroundings, exclude=(back,))
        if not turns:
            return back
        return self._rng.choice(turns)
