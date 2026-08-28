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
    """A rectangular grid of cells, each either open corridor or wall.

    Nothing here knows about characters, colours or sprites, which is what
    lets a maze be built, queried and asserted about without a terminal.
    """

    def __init__(self, open_cells: Grid) -> None:
        """Wraps a grid of booleans, one per cell, as a maze.

        Args:
            open_cells: Rows of booleans, True where the cell is corridor.
                The grid is copied, so later edits to it do not reach the
                maze.

        Raises:
            ValueError: If the grid is empty, or its rows are not all the
                same length.
        """
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
        """Carves a random maze of this size and braids its dead ends away.

        The outermost cells are always wall, so the result has a border.

        Args:
            rows: Height of the maze in cells.
            cols: Width of the maze in cells.
            seed: Seed for the carving. A seed makes the maze reproducible,
                which is the only way a test can assert anything about a
                particular one. None gives a different maze every time.

        Returns:
            A braided maze of that size, with a wall border and no dead ends.

        Raises:
            ValueError: If the size leaves no room for junctions, which needs
                at least three rows and three columns.
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
        """Builds a maze from lines of text, for tests that need a known shape.

            Maze.from_rows(["#####",
                            "#...#",
                            "#.#.#",
                            "#...#",
                            "#####"])

        Args:
            rows: One string per cell row, all of the same length.
            open_char: The character that marks corridor. Any other character
                is wall.

        Returns:
            A maze of exactly the shape those rows describe.
        """
        return cls([[ch == open_char for ch in row] for row in rows])

    # -- shape -----------------------------------------------------------

    @property
    def rows(self) -> int:
        """The height of the maze in cells."""
        return len(self._open)

    @property
    def cols(self) -> int:
        """The width of the maze in cells."""
        return len(self._open[0])

    def is_open(self, row: int, col: int) -> bool:
        """Reports whether a cell is corridor.

        Args:
            row: Cell row.
            col: Cell column.

        Returns:
            True if the cell is corridor. Out of bounds counts as wall.
        """
        return 0 <= row < self.rows and 0 <= col < self.cols and self._open[row][col]

    def open_cells(self) -> Tuple[Cell, ...]:
        """Returns every corridor cell, in row-major order."""
        return tuple(
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
            if self._open[row][col]
        )

    def wall_cells(self) -> Tuple[Cell, ...]:
        """Returns every wall cell, in row-major order."""
        return tuple(
            (row, col)
            for row in range(self.rows)
            for col in range(self.cols)
            if not self._open[row][col]
        )

    def neighbours(self, row: int, col: int) -> Tuple[Cell, ...]:
        """Returns the cells adjacent to one cell, wall or not.

        Args:
            row: Cell row.
            col: Cell column.

        Returns:
            The neighbours that fall inside the grid, north, south, west and
            east in that order.
        """
        return tuple(
            (row + d_row, col + d_col)
            for d_row, d_col in _NEIGHBOUR_STEPS
            if 0 <= row + d_row < self.rows and 0 <= col + d_col < self.cols
        )

    def open_neighbours(self, row: int, col: int) -> Tuple[Cell, ...]:
        """Returns the corridor cells adjacent to one cell.

        Args:
            row: Cell row.
            col: Cell column.

        Returns:
            The neighbours from `neighbours` that are corridor, so the ways
            out of this cell.
        """
        return tuple(c for c in self.neighbours(row, col) if self._open[c[0]][c[1]])

    # -- the properties this maze promises -------------------------------

    def dead_ends(self) -> Tuple[Cell, ...]:
        """Returns the open cells with fewer than two ways out.

        A braided maze has none. This returns the cells rather than a
        yes-or-no so that a failure says *where*.
        """
        return tuple(
            cell
            for cell in self.open_cells()
            if len(self.open_neighbours(*cell)) < 2
        )

    def reachable_from(self, row: int, col: int) -> FrozenSet[Cell]:
        """Returns every open cell that can be walked to from one cell.

        Args:
            row: Cell row to start from.
            col: Cell column to start from.

        Returns:
            The cells reachable from there, including the starting cell, or an
            empty set if the starting cell is wall.
        """
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
        """Reports whether every open cell can be reached from every other.

        Returns:
            True if the corridors form one connected region. An empty maze
            counts as connected.
        """
        cells = self.open_cells()
        if not cells:
            return True
        return len(self.reachable_from(*cells[0])) == len(cells)

    def islands(self) -> Tuple[FrozenSet[Cell], ...]:
        """Returns the wall regions that do not touch the border.

        These are the solid blocks the corridors run around. They hold no dots
        because they hold no open cells, which is true by construction rather
        than by anything having to go looking for them.

        Returns:
            One frozen set of cells per island, in no particular order.
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
        """Returns the open cell closest to a wanted spot.

        Args:
            row: Row of the wanted spot, which may itself be wall.
            col: Column of the wanted spot.

        Returns:
            The corridor cell at the smallest distance from that spot.
        """
        return min(self.open_cells(), key=lambda c: _distance(c, (row, col)))

    def farthest_open(self, row: int, col: int) -> Cell:
        """Returns the open cell furthest from a spot.

        Paired with `nearest_open`, this is what keeps two things placed by
        these two calls from starting on top of each other, whatever shape the
        maze took.

        Args:
            row: Row of the spot to get away from.
            col: Column of the spot to get away from.

        Returns:
            The corridor cell at the greatest distance from that spot.
        """
        return max(self.open_cells(), key=lambda c: _distance(c, (row, col)))

    # -- generation ------------------------------------------------------

    def _carve(
        self, rng: random.Random, junction_rows: Tuple[int, ...],
        junction_cols: Tuple[int, ...],
    ) -> None:
        """Carves a perfect maze, dead ends and all.

        A depth-first walk between junctions, opening the wall between each
        pair as it goes.

        Args:
            rng: Source of randomness for the walk.
            junction_rows: The rows junctions sit on, every other row.
            junction_cols: The columns junctions sit on, every other column.
        """
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
        """Opens a second way out of every junction that has only one.

        Opening a wall raises the count for two junctions at once and never
        lowers one, so this only has to sweep until a pass changes nothing.
        Every junction has at least two neighbours, even in a corner, so a
        second exit can always be found -- which is what makes "no dead ends"
        a guarantee rather than an attempt.

        Args:
            rng: Source of randomness for choosing which wall to open.
            junction_rows: The rows junctions sit on, every other row.
            junction_cols: The columns junctions sit on, every other column.
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
        """Draws the maze as text, for a test failure message or a print.

        Args:
            wall: The character to draw wall cells with.
            corridor: The character to draw open cells with.

        Returns:
            One string per cell row.
        """
        return tuple(
            "".join(corridor if cell else wall for cell in row)
            for row in self._open
        )

    def __repr__(self) -> str:
        """Returns the maze's size and how much of it is corridor."""
        return "Maze({}x{}, {} open cells)".format(
            self.rows, self.cols, len(self.open_cells())
        )


def _distance(a: Cell, b: Cell) -> int:
    """Returns the distance between two cells, counted in moves.

    Manhattan rather than straight-line, because a sprite moves one cell at a
    time along the grid and never diagonally.
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
