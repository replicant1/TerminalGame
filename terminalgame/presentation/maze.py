"""A rectangular grid of cells, each either wall or open corridor.

Knows nothing about characters, colours or sprites: a cell is open or it is
not. That is what lets a maze be built, queried and asserted about without a
terminal, and what lets a test build one by hand from a few lines of text.

Two ideas run through the generation, and they are worth separating.

A **perfect** maze has exactly one route between any two cells. Carving one is
the easy part -- a depth-first walk between junctions does it -- but a perfect
maze is nothing but dead ends, because every branch that is not the route to
somewhere terminates.

**Braiding** is the pass that removes them. Wherever a junction has only one
way out, a second is opened. That destroys the perfectness on purpose: the
maze gains loops, and the wall between two corridors that were joined becomes
part of an island rather than part of the border.
"""

import random
from typing import FrozenSet, Iterable, Iterator, List, Optional, Sequence, Tuple

Cell = Tuple[int, int]
Grid = List[List[bool]]

# North, south, west, east. One cell apart for walking, two for carving.
_NEIGHBOUR_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_JUNCTION_STEPS = ((-2, 0), (2, 0), (0, -2), (0, 2))


class Maze:
    """A grid of cells. Open cells are corridor, the rest are wall."""

    def __init__(self, open_cells: Grid) -> None:
        if not open_cells or not open_cells[0]:
            raise ValueError("a maze needs at least one cell")
        width = len(open_cells[0])
        if any(len(row) != width for row in open_cells):
            raise ValueError("every row of a maze must be the same length")
        self._open = [list(row) for row in open_cells]

    # -- construction ----------------------------------------------------

    @classmethod
    def generate(
        cls, rows: int, cols: int, seed: Optional[int] = None
    ) -> "Maze":
        """Carve a random maze of this size and braid its dead ends away.

        The outermost cells are always wall, so the result has a border. A
        seed makes the maze reproducible, which is the only way a test can
        assert anything about a particular one.
        """
        junction_rows = tuple(range(1, rows - 1, 2))
        junction_cols = tuple(range(1, cols - 1, 2))
        if not junction_rows or not junction_cols:
            raise ValueError(
                "a maze of {}x{} has no room for junctions - it needs at "
                "least 3 rows and 3 columns".format(rows, cols)
            )

        rng = random.Random(seed)
        grid: Grid = [[False] * cols for _ in range(rows)]
        maze = cls(grid)
        maze._carve(rng, junction_rows, junction_cols)
        maze._braid(rng, junction_rows, junction_cols)
        return maze

    @classmethod
    def from_rows(cls, rows: Sequence[str], open_char: str = ".") -> "Maze":
        """Build a maze from lines of text, for tests that need a known shape.

            Maze.from_rows(["#####",
                            "#...#",
                            "#.#.#",
                            "#...#",
                            "#####"])

        Any character other than `open_char` is wall.
        """
        return cls([[ch == open_char for ch in row] for row in rows])

    # -- shape -----------------------------------------------------------

    @property
    def rows(self) -> int:
        return len(self._open)

    @property
    def cols(self) -> int:
        return len(self._open[0])

    def is_open(self, row: int, col: int) -> bool:
        """True if this cell is corridor. Out of bounds counts as wall."""
        return 0 <= row < self.rows and 0 <= col < self.cols and self._open[row][col]

    def open_cells(self) -> Tuple[Cell, ...]:
        return tuple(
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
            if self._open[row][col]
        )

    def wall_cells(self) -> Tuple[Cell, ...]:
        return tuple(
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
            if not self._open[row][col]
        )

    def neighbours(self, row: int, col: int) -> Tuple[Cell, ...]:
        """The cells adjacent to this one, wall or not, inside the grid."""
        return tuple(
            (row + d_row, col + d_col)
            for d_row, d_col in _NEIGHBOUR_STEPS
            if 0 <= row + d_row < self.rows and 0 <= col + d_col < self.cols
        )

    def open_neighbours(self, row: int, col: int) -> Tuple[Cell, ...]:
        return tuple(c for c in self.neighbours(row, col) if self._open[c[0]][c[1]])

    # -- the properties this maze promises -------------------------------

    def dead_ends(self) -> Tuple[Cell, ...]:
        """Open cells with fewer than two ways out.

        A braided maze has none. This returns them rather than a yes-or-no so
        that a failure says *where*.
        """
        return tuple(
            cell
            for cell in self.open_cells()
            if len(self.open_neighbours(*cell)) < 2
        )

    def reachable_from(self, row: int, col: int) -> FrozenSet[Cell]:
        """Every open cell that can be walked to from here."""
        if not self.is_open(row, col):
            return frozenset()
        seen = {(row, col)}
        pending = [(row, col)]
        while pending:
            cell = pending.pop()
            for neighbour in self.open_neighbours(*cell):
                if neighbour not in seen:
                    seen.add(neighbour)
                    pending.append(neighbour)
        return frozenset(seen)

    def is_fully_connected(self) -> bool:
        """True if every open cell can be reached from every other."""
        cells = self.open_cells()
        if not cells:
            return True
        return len(self.reachable_from(*cells[0])) == len(cells)

    def islands(self) -> Tuple[FrozenSet[Cell], ...]:
        """Wall regions that do not touch the border.

        These are the solid blocks the corridors run around. They hold no dots
        because they hold no open cells, which is true by construction rather
        than by anything having to go looking for them.
        """
        found: List[FrozenSet[Cell]] = []
        seen = set()
        for cell in self.wall_cells():
            if cell in seen:
                continue
            region, pending, touches_border = set(), [cell], False
            seen.add(cell)
            while pending:
                row, col = pending.pop()
                region.add((row, col))
                if row in (0, self.rows - 1) or col in (0, self.cols - 1):
                    touches_border = True
                for neighbour in self.neighbours(row, col):
                    if not self._open[neighbour[0]][neighbour[1]] and neighbour not in seen:
                        seen.add(neighbour)
                        pending.append(neighbour)
            if not touches_border:
                found.append(frozenset(region))
        return tuple(found)

    # -- picking somewhere to stand --------------------------------------

    def nearest_open(self, row: int, col: int) -> Cell:
        """The open cell closest to a wanted spot, which may itself be wall."""
        return min(self.open_cells(), key=lambda c: _distance(c, (row, col)))

    def farthest_open(self, row: int, col: int) -> Cell:
        """The open cell furthest from a spot, so two things placed with these
        two calls do not start on top of each other whatever shape the maze
        took."""
        return max(self.open_cells(), key=lambda c: _distance(c, (row, col)))

    # -- generation ------------------------------------------------------

    def _carve(
        self, rng: random.Random, junction_rows: Tuple[int, ...],
        junction_cols: Tuple[int, ...],
    ) -> None:
        """Depth-first walk between junctions, opening the wall between each
        pair as it goes. Produces a perfect maze, dead ends and all."""
        def is_junction(row: int, col: int) -> bool:
            return row in junction_rows and col in junction_cols

        start = (rng.choice(junction_rows), rng.choice(junction_cols))
        self._open[start[0]][start[1]] = True
        stack = [start]
        while stack:
            row, col = stack[-1]
            unvisited = [
                (row + d_row, col + d_col)
                for d_row, d_col in _JUNCTION_STEPS
                if is_junction(row + d_row, col + d_col)
                and not self._open[row + d_row][col + d_col]
            ]
            if not unvisited:
                stack.pop()
                continue
            next_row, next_col = rng.choice(unvisited)
            self._open[(row + next_row) // 2][(col + next_col) // 2] = True
            self._open[next_row][next_col] = True
            stack.append((next_row, next_col))

    def _braid(
        self, rng: random.Random, junction_rows: Tuple[int, ...],
        junction_cols: Tuple[int, ...],
    ) -> None:
        """Open a second way out of every junction that has only one.

        Opening a wall raises the count for two junctions at once and never
        lowers one, so this only has to sweep until a pass changes nothing.
        Every junction has at least two neighbours, even in a corner, so a
        second exit can always be found -- which is what makes "no dead ends"
        a guarantee rather than an attempt.
        """
        def is_junction(row: int, col: int) -> bool:
            return row in junction_rows and col in junction_cols

        while True:
            changed = False
            for row in junction_rows:
                for col in junction_cols:
                    if not self._open[row][col]:
                        continue
                    exits, closed = 0, []
                    for d_row, d_col in _JUNCTION_STEPS:
                        if not is_junction(row + d_row, col + d_col):
                            continue
                        wall = (row + d_row // 2, col + d_col // 2)
                        if self._open[wall[0]][wall[1]]:
                            exits += 1
                        else:
                            closed.append((wall, (row + d_row, col + d_col)))
                    if exits > 1 or not closed:
                        continue
                    wall, junction = rng.choice(closed)
                    self._open[wall[0]][wall[1]] = True
                    self._open[junction[0]][junction[1]] = True
                    changed = True
            if not changed:
                return

    # -- for looking at --------------------------------------------------

    def to_rows(self, wall: str = "#", corridor: str = ".") -> Tuple[str, ...]:
        """One string per cell row, for a test failure message or a print."""
        return tuple(
            "".join(corridor if cell else wall for cell in row)
            for row in self._open
        )

    def __repr__(self) -> str:
        return "Maze({}x{}, {} open cells)".format(
            self.rows, self.cols, len(self.open_cells())
        )


def _distance(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
