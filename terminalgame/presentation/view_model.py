"""Game logic. Owns the state, knows nothing about curses.

The screen never asks the ViewModel for anything -- it subscribes once and is
pushed a complete ViewState whenever something changes.
"""

import random
from typing import Optional, Tuple

from ..util.flow import StateFlow
from .maze import Maze
from .state import (
    CELL_COLS,
    CELL_ROWS,
    COLOR_GHOST,
    COLOR_PLAYER,
    GRID_COLS,
    GRID_ROWS,
    Sprite,
    ViewState,
)

# One cell of wall and one of open corridor, each CELL_ROWS strings of
# CELL_COLS characters. Block glyphs rather than box-drawing: walls here are
# solid regions rather than outlines, so there are no corners to draw.
#
# A corridor carries exactly one dot, because a sprite occupies one cell and a
# dot marks one place a sprite can stand. Two dots in a cell would say there
# were two such places.
#
# The dot is a pair of quadrant blocks: lower-right, then lower-left. Each
# fills the quarter of its own character nearest the other, so back to back
# they meet and read as one small solid block with a gap either side -- a
# single pellet, rather than a mark at one edge of the cell.
#
# Quadrants rather than half blocks because a half block pair fills the cell's
# full height, which at this size reads as a bar rather than a pellet. The
# quadrant pair is half as tall and very nearly square.
# The pill sits in the *left* character of its cell, because that is where a
# wall's line sits too -- a cell is two characters wide and one tall, so there
# is no column between them for a vertical line to occupy, and the left column
# is the centre line everything has to share.
#
# Put the pill anywhere else and it stops being centred. A pill straddling the
# two characters lands half a character to the right of the corridor's middle,
# and one drawn with quadrant blocks sits on the floor of the row while the
# horizontal walls run through the middle of theirs. A small square centred in
# its own character is centred both ways at once.
_PILL = "▪"

# How a game ended. Two ways out: the arena is cleared, or the ghost catches
# the player. They are told apart because the line of readings says which
# happened, and because a capture draws the ghost on top of the player.
_CLEARED = "cleared"
_CAUGHT = "caught"
_PILL_CELL = (_PILL + " " * (CELL_COLS - 1),) * CELL_ROWS

# Walls are drawn as lines rather than solid blocks, so a wall cell needs to
# know which of its neighbours are also wall before it can pick a glyph. The
# four bits below say which sides a line leaves by.
_NORTH, _SOUTH, _WEST, _EAST = 1, 2, 4, 8

# The line leaving each side, by the set of sides it has. Double lines: they
# carry more weight than the single-line set at this size, which matters when
# a wall is one cell thick and has pills either side of it.
#
# A cell with a single arm is drawn as the through-line rather than a stub.
# The single-line set at least has half-lines to reach for; the double-line
# set has none at all, so there is nothing else it could be.
_WALL_GLYPH = {
    # A one-cell island has no line to join, so it is a pillar rather than a
    # length of wall: a filled square, centred in the cell's left character
    # like everything else, and larger than a pill so the two do not read as
    # the same thing.
    0: "■",
    _NORTH: "║", _SOUTH: "║", _NORTH | _SOUTH: "║",
    _WEST: "═", _EAST: "═", _WEST | _EAST: "═",
    _NORTH | _EAST: "╚", _NORTH | _WEST: "╝",
    _SOUTH | _EAST: "╔", _SOUTH | _WEST: "╗",
    _NORTH | _SOUTH | _EAST: "╠", _NORTH | _SOUTH | _WEST: "╣",
    _SOUTH | _WEST | _EAST: "╦", _NORTH | _WEST | _EAST: "╩",
    _NORTH | _SOUTH | _WEST | _EAST: "╬",
}
# What a layer holds where the other layer has something. GameScreen skips
# these rather than drawing them: a space is a character like any other, and
# writing one would paint over whatever the earlier pass put there.
_BLANK_CELL = (" " * CELL_COLS,) * CELL_ROWS

# Sprites sit on the same centre line as the walls and the pills, and are drawn
# centred on it -- which is why their art has an *odd* number of characters.
# Ink centred on a character's middle can be one character wide, or three, but
# never two: two characters are centred on the join between them, half a
# character off the line everything else sits on.
#
# Three characters with half blocks at the edges gives two characters' worth of
# ink, which is the full width of a corridor, while still being centred. It
# overhangs into the blank right-hand character of the cell either side, and
# those are always blank next to an open cell: a wall only carries its line
# eastward when the next cell is also wall.
#
# The player is a solid block. The ghost has a full-height middle with lower
# halves either side, so it reads as narrower on top and wider at the foot,
# and the two are told apart by shape as well as by colour.
_PLAYER_ART = ("▐█▌",)
_GHOST_ART = ("▗█▖",)

# Art with an even width cannot be centred on the corridor's centre line, and
# art of the wrong height would spill into the row above or below. Cheap to
# check once, at import, rather than discovering it as a drawing that looks
# very slightly wrong.
for _name, _art in (("player", _PLAYER_ART), ("ghost", _GHOST_ART)):
    if len(_art) != CELL_ROWS:
        raise ValueError(
            "{} art is {} rows, but a cell is {}".format(
                _name, len(_art), CELL_ROWS
            )
        )
    _widths = {len(_line) for _line in _art}
    if len(_widths) != 1:
        raise ValueError(
            "{} art has rows of differing widths {} - a sprite is a "
            "rectangle".format(_name, sorted(_widths))
        )
    _width = _widths.pop()
    if _width % 2 == 0:
        raise ValueError(
            "{} art is {} characters wide - sprite art has to be an odd "
            "width to sit centred on the corridor".format(_name, _width)
        )

def _odd(size: int) -> int:
    """Returns the largest odd number of cells that fits.

    A maze needs a wall cell on both sides of every junction, so its border
    only comes out one cell thick if it is an odd number of cells across.
    Given an even number, the last column has no junction to serve and is
    drawn as a second border running alongside the first -- invisible while
    walls were solid blocks, and an obvious ladder once they became lines.

    Args:
        size: How many cells are available.

    Returns:
        `size`, or one less when `size` is even.
    """
    return size if size % 2 else size - 1


def _wall_cell(maze, row: int, col: int) -> str:
    """Draws one wall cell as CELL_COLS characters.

    A cell's line meets its neighbours' lines in the *left* of its two
    characters, which is therefore the wall's centre line. That is the only
    way vertical runs can line up: a cell is two characters wide and one tall,
    so there is no column between them for a vertical line to sit in. A
    horizontal run then reaches its neighbour through the right-hand
    character, which carries a dash whenever the cell continues eastwards.

    Out of bounds counts as not-wall, which is what closes the border into a
    rectangle instead of leaving it with arms pointing off the playfield.

    Args:
        maze: The maze being drawn, asked which of the neighbours are wall.
        row: Cell row.
        col: Cell column.

    Returns:
        The characters for that cell: the glyph for the sides it joins, then a
        dash where the wall continues eastwards and a blank where it does not.
    """
    def wall(r: int, c: int) -> bool:
        """Reports whether that cell is wall, counting out of bounds as not."""
        return 0 <= r < maze.rows and 0 <= c < maze.cols and not maze.is_open(r, c)

    sides = 0
    if wall(row - 1, col):
        sides |= _NORTH
    if wall(row + 1, col):
        sides |= _SOUTH
    if wall(row, col - 1):
        sides |= _WEST
    if wall(row, col + 1):
        sides |= _EAST
    # The right-hand character carries the line onward only when the cell
    # really does continue eastwards into another wall. Filling it in any
    # other case leaves the wall touching the pill in the next cell, with none
    # of the gap every other wall cell leaves.
    return _WALL_GLYPH[sides] + ("═" if sides & _EAST else " ")


def _to_layers(maze) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Turns a Maze into the two character layers GameScreen draws.

    Every open cell gets its one pill. Wall cells get none, so the solid
    islands braiding leaves behind come out blank inside without anything
    having to go looking for them: a cell that was never carved is simply
    never given a pill.

    Args:
        maze: The maze to draw.

    Returns:
        The walls and the pills, in that order, each blank where the other has
        something -- because a layer is drawn in a single colour.
    """
    walls, pills = [], []
    for cell_row in range(maze.rows):
        wall_lines = [""] * CELL_ROWS
        pill_lines = [""] * CELL_ROWS
        for cell_col in range(maze.cols):
            open_cell = maze.is_open(cell_row, cell_col)
            wall = (
                _BLANK_CELL
                if open_cell
                else (_wall_cell(maze, cell_row, cell_col),) * CELL_ROWS
            )
            pill = _PILL_CELL if open_cell else _BLANK_CELL
            for i in range(CELL_ROWS):
                wall_lines[i] += wall[i]
                pill_lines[i] += pill[i]
        walls.extend(wall_lines)
        pills.extend(pill_lines)
    return tuple(walls), tuple(pills)


class GameViewModel:
    """Turns ticks and key presses into ViewStates.

    Owns the maze, the score and where everything stands. Knows nothing about
    curses: it publishes frames and never learns who is collecting them.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        """Carves a maze, places the player and the ghost, and paints frame one.

        Args:
            seed: Seed for the maze and the ghost's choices. A seed makes a
                game reproducible, which is what lets a test assert anything
                about one. None gives a different maze every run.
        """
        # A seed makes a maze reproducible, which is what lets a test assert
        # anything about one. Left out, every run gets a different maze.
        self._maze = Maze.generate(_odd(GRID_ROWS), _odd(GRID_COLS), seed=seed)
        self._walls, self._pills = _to_layers(self._maze)
        self._rng = random.Random(seed)
        self._tick_count = 0
        # Positions are in game cells, not characters. Both have to start on
        # open corridor, which no fixed coordinate can promise once the maze
        # is random.
        self._player_row, self._player_col = self._maze.nearest_open(
            GRID_ROWS // 2, GRID_COLS // 2
        )
        self._ghost_row, self._ghost_col = self._maze.farthest_open(
            self._player_row, self._player_col
        )
        self._ghost_step = (0, 1)
        # The pill layer is no longer fixed for the game, so it is kept as a
        # mutable list of rows and re-frozen into `self._pills` each time one
        # is eaten -- once per pill, not once per frame.
        self._pill_rows = list(self._pills)
        self._pills_left = sum(row.count(_PILL) for row in self._pill_rows)
        self._score = 0
        self._ending: Optional[str] = None
        # The player starts standing on a corridor cell, which has a pill on
        # it. Taking it silently, without scoring, is what makes the opening
        # score 0 rather than 1, and stops a pill nobody can see from being
        # the one the game is waiting on.
        self._take_pill(self._player_row, self._player_col)
        self._state: StateFlow[ViewState] = StateFlow(self._build_state())

    @property
    def state(self) -> StateFlow[ViewState]:
        """The flow GameScreen collects frames from."""
        return self._state

    # -- inputs ----------------------------------------------------------

    def tick(self) -> None:
        """Advances the simulation by one step. Called by GameClock.

        A finished game stops advancing: the ghost stands still, the tick
        count stops, and the frame the player is looking at is the last one
        that will be published until they quit.

        This is one of the two moments a capture can happen -- the ghost
        walking onto the player. The other is the player walking onto the
        ghost, in `on_direction`.
        """
        if self._ending is not None:
            return
        self._tick_count += 1
        self._advance_ghost()
        if self._sharing_a_cell():
            self._ending = _CAUGHT
        self._publish()

    def on_direction(self, d_row: int, d_col: int) -> None:
        """Moves the player one cell, eating the pill it lands on.

        Called by GameScreen when an arrow key arrives. One press moves one
        whole cell, so the player never lands straddling two of them. A press
        into a wall does nothing, which leaves the frame identical and costs
        the terminal nothing, and a finished game ignores the press entirely.

        Args:
            d_row: -1, 0 or 1, the rows to move by.
            d_col: -1, 0 or 1, the columns to move by.
        """
        if self._ending is not None:
            return
        row, col = self._player_row + d_row, self._player_col + d_col
        if self._maze.is_open(row, col):
            self._player_row, self._player_col = row, col
            if self._take_pill(row, col):
                self._score += 1
            # Walking onto the ghost is a capture, and it is checked before
            # the pills are counted: a player who takes the last pill off the
            # cell the ghost is standing on has still walked into the ghost.
            if self._sharing_a_cell():
                self._ending = _CAUGHT
            elif self._pills_left == 0:
                self._ending = _CLEARED
            self._publish()

    # -- internals -------------------------------------------------------

    def _take_pill(self, row: int, col: int) -> bool:
        """Clears the pill in one cell, if it still has one.

        A pill sits in the *left* character of its cell, the same centre line
        the walls and sprites share, so one cell is one character to blank.
        The row is rebuilt rather than mutated because the published layer is
        a tuple of strings and has to stay one.

        Args:
            row: Cell row.
            col: Cell column.

        Returns:
            True if there was a pill there to take, so the caller knows
            whether to score it.
        """
        char_row, char_col = row * CELL_ROWS, col * CELL_COLS
        line = self._pill_rows[char_row]
        if line[char_col] != _PILL:
            return False
        self._pill_rows[char_row] = (
            line[:char_col] + " " + line[char_col + 1:]
        )
        self._pills = tuple(self._pill_rows)
        self._pills_left -= 1
        return True

    def _sharing_a_cell(self) -> bool:
        """Reports whether the player and the ghost are standing on one cell.

        A cell, not a character position: the two sprites overlap on screen
        whenever they are within a character of each other, but only one cell
        holds them both.

        There is no need to look for the pair swapping places, which is the
        usual way a collision check is fooled. Nothing here moves at the same
        time as anything else -- the ghost moves on a tick and the player on a
        key press, one after another on one thread -- so a pass-through would
        need two moves, and the check runs after each of them.

        Returns:
            True if the ghost has the player, however the two came to be
            there.
        """
        return (self._player_row, self._player_col) == (
            self._ghost_row, self._ghost_col
        )

    def _advance_ghost(self) -> None:
        """Moves the ghost one cell, carrying straight on where possible.

        Because the maze has no dead ends, a ghost that has just arrived
        somewhere always has a way on that is not the way it came. Reversing
        is a last resort rather than the usual outcome.
        """
        d_row, d_col = self._ghost_step
        ahead = (self._ghost_row + d_row, self._ghost_col + d_col)
        if self._maze.is_open(*ahead):
            self._ghost_row, self._ghost_col = ahead
            return
        back = (-d_row, -d_col)
        turns = [
            step
            for step in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if step != back
            and self._maze.is_open(self._ghost_row + step[0], self._ghost_col + step[1])
        ]
        if not turns:
            turns = [back]
        self._ghost_step = self._rng.choice(turns)
        self._ghost_row += self._ghost_step[0]
        self._ghost_col += self._ghost_step[1]

    def _status_line(self) -> str:
        """Builds the row of readings under the playfield.

        The score and the keys, and nothing else. The tick count and the
        player's cell were readings for whoever was building the thing rather
        than anyone playing it, and a player reading their own coordinates off
        the bottom of the screen is a player being told what the maze already
        shows them.

        A finished game says which of the two ways it finished, in the same
        shape either way: the word, the score, the key that leaves. A line
        reading GAME OVER after a ghost walked into somebody says what
        happened but not why, and the two endings are worth telling apart at a
        glance -- which the frame does as well, by drawing the ghost on top.

        The last row loses its final cell to curses, so the budget is
        PLAYFIELD_COLS - 1, which is 39. No line comes near it: three digits
        hold a maze this size, which is a few hundred pills, and a fourth
        would still fit.
        """
        if self._ending == _CAUGHT:
            return " CAUGHT  score {:<3}  q quits".format(self._score)
        if self._ending == _CLEARED:
            return " GAME OVER  score {:<3}  q quits".format(self._score)
        return " score {:<3}  arrows, q quits".format(self._score)

    def _publish(self) -> None:
        """Builds the current frame and offers it to the flow."""
        # StateFlow drops this silently if nothing actually changed.
        self._state.emit(self._build_state())

    def _build_state(self) -> ViewState:
        """Assembles one frame from where everything currently stands.

        Returns:
            A frame carrying both maze layers, the two sprites in character
            coordinates, and the status line.
        """
        # Cell coordinates become character coordinates here, and nowhere else.
        ghost = Sprite(
            self._ghost_row * CELL_ROWS,
            self._ghost_col * CELL_COLS - len(_GHOST_ART[0]) // 2,
            _GHOST_ART, COLOR_GHOST,
        )
        player = Sprite(
            self._player_row * CELL_ROWS,
            self._player_col * CELL_COLS - len(_PLAYER_ART[0]) // 2,
            _PLAYER_ART, COLOR_PLAYER,
        )
        # Sprites are drawn in order, so the last one wins where they overlap.
        # The player is normally on top, which is what keeps it visible as the
        # ghost passes. On a capture that is exactly wrong: the player would
        # hide the thing that caught them, and the final frame would look like
        # any other. So the ghost goes last, and the last frame shows it.
        sprites = (player, ghost) if self._ending == _CAUGHT else (ghost, player)
        return ViewState(
            walls=self._walls,
            pills=self._pills,
            sprites=sprites,
            status_line=self._status_line(),
            tick=self._tick_count,
        )
