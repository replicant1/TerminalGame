# Glossary

Every recurring term in this codebase and its documents, what it means here,
and where it is defined. Words like *cell*, *layer* and *sentinel* are ordinary
English doing specific jobs, and most of the confusion in reading this program
comes from carrying the ordinary meaning into a place that wanted the specific
one.

## The distinction to get straight first

**A cell is not a character position, and the game counts in cells.**

The playfield is 30 character rows by 40 character columns, because that is the
size the terminal window is made. But a game cell is one character row by
**two** character columns, so the maze is 29 by 20 cells with the bottom row
given over to the status line. Positions, movement and collisions are all
counted in cells; the conversion to character coordinates happens in exactly
one place, where `GameViewModel` builds its sprites, so `GameScreen` is handed
character positions and never learns that cells exist.

The reason a cell is 1x2 rather than square is that a terminal's character is
about twice as tall as it is wide — 11.9 by 24.6 points at the size the
launcher asks for — so one row by two columns comes out very nearly square on
screen, at 23.9 by 24.6. A 2x2 cell would be a tall rectangle.

When a document says *row* and *col* without qualification, read the
surrounding code: `Maze` and `GameViewModel` mean cells, `Sprite` and
`GameScreen` mean characters.

## The maze

Defined in [`presentation/maze.py`](../terminalgame/presentation/maze.py),
which knows nothing about characters, colours or sprites.

| Term | What it means here |
|---|---|
| **cell** | One square of the grid, either open or wall. The unit the game's logic counts in |
| **open cell**, **corridor** | A cell something can stand in or walk through |
| **wall cell** | A cell nothing can enter. The outermost cells are always wall, which is what gives the maze its border |
| **junction** | A cell on an odd row and odd column — the lattice the carving walks between. Everything else is either wall or a passage opened between two junctions |
| **carve** | The depth-first walk that opens passages between junctions, producing a maze with exactly one route between any two cells |
| **perfect** | Having exactly one route between any two cells. What carving produces, and what braiding deliberately destroys |
| **braid** | The pass that removes dead ends by opening a second way out of every cell that has only one. It costs the maze its perfectness and gains it loops |
| **dead end** | An open cell with fewer than two ways out. A braided maze has none, and `_dead_ends()` returns the cells rather than a yes or no so a failing test can say *where* |
| **island** | A region of wall that does not touch the border — what a braided-away wall becomes, and the reason the maze looks like a maze rather than a comb |
| **fully connected** | Every open cell reachable from every other. Checked, not assumed |
| **seed** | The number that fixes the random choices, so the same seed gives the same maze every run. Passed to `Maze.generate` and to `GameViewModel` |

The carving and braiding passes are easier watched than read:
[carving and braiding, one step at a time](https://replicant1.github.io/TerminalGame/docs/step-by-step/maze-step-by-step.html)
builds an eleven by eleven maze one decision at a time.

## The frame

Defined in [`presentation/state.py`](../terminalgame/presentation/state.py) and
built in [`presentation/view_model.py`](../terminalgame/presentation/view_model.py).

| Term | What it means here |
|---|---|
| **playfield** | The fixed 30x40 block of character positions the game is drawn into. The terminal window is resized to match at startup |
| **frame**, **ViewState** | Everything needed to draw one complete picture: both layers, the sprites, the status line and the tick count. Immutable, and complete — there are no deltas |
| **layer** | One of the two backgrounds, each a tuple of strings, one per character row. There are two rather than one because a layer is drawn in a single colour |
| **wall layer** | The maze itself, blank wherever the pill layer has something |
| **pill layer** | The pellets, blank wherever the wall layer has something |
| **glyph** | The character drawn for a cell. A wall cell picks a box-drawing line from a four-bit mask saying which of its neighbours are also wall, so the walls join up |
| **pill**, **pellet** | The `▪` a player eats for a point. One per corridor cell, in the *left* character of the cell, which is the centre line the walls share |
| **sprite** | Something that moves, drawn on top of both layers: a block of art at a character position, in one colour. The player and the ghost are the only two |
| **art** | A sprite's characters, one string per character row. Its width is odd, so it can sit centred on the corridor's centre line |
| **colour slot** | A logical colour — `COLOR_WALL`, `COLOR_PILL`, `COLOR_GHOST` and so on. `GameScreen` maps these onto curses colour pairs, so nothing in `presentation` imports curses |
| **status line** | The bottom character row: the score, the keys, and on a finished game which of the two endings happened |
| **tick count** | How many times the clock has fired, carried on the frame so a test can tell two otherwise identical frames apart |

A wall cell choosing its glyph is the other pass with a page of its own:
[every wall cell picks its glyph](https://replicant1.github.io/TerminalGame/docs/step-by-step/wall-glyphs-step-by-step.html).

## The moving parts

Defined in [`util/`](../terminalgame/util) and driven from
[`app/main.py`](../terminalgame/app/main.py).

| Term | What it means here |
|---|---|
| **tick** | One fixed-timestep step of the simulation, every 0.15 seconds. The ghost moves on a tick; the player does not, moving on a key instead |
| **poll** | Asking the clock whether a tick is due. The clock never runs on its own, because a tick arriving on another thread while the main one is mid-refresh would corrupt the screen |
| **StateFlow** | A value that can be watched: it always holds something, a new subscriber is handed the current value at once, and emitting a value equal to the one held does nothing |
| **emit** | Offering a new value to the flow. An emission equal to the last one is dropped, which is what keeps an idle game from writing to the terminal at all |
| **subscriber**, **collector** | A function handed every new value. There is exactly one in the running game — `GameScreen.render` |
| **attach** | `GameScreen` subscribing to the ViewModel, which paints the first frame immediately as a side effect of subscribing |
| **composition root** | `app/`, the only package that imports from every other one and the only place the objects are wired together |

## The window

Defined in [`app/launcher.py`](../terminalgame/app/launcher.py). None of this
is game logic; it is what makes `python3 -m terminalgame.app.main` behave like
an ordinary command while the game runs somewhere else.

| Term | What it means here |
|---|---|
| **launcher** | The process you started, which opens the game's window and then waits. It does not play the game |
| **child** | The second process, running the game inside the new window. It knows it is the child because the launcher set `TERMINALGAME_CHILD=1` in its environment |
| **sentinel** | A small file in a temporary directory that the child writes twice — `pid 1234` when it starts, `exit 0` when it finishes — and the launcher polls ten times a second. It is the only channel between the two processes |
| **spawn** | Asking Terminal.app, through `osascript`, to open a window of exactly the right size and run the game in it |
| **osascript** | The macOS command that runs AppleScript. How a window gets created, sized, positioned and later closed |
| **tty** | The terminal device of the new tab, used to work out which window contains it. Matching by title is unreliable, because Terminal puts the running command in the title |
| **`--here`** | Play in the terminal you are already in, spawning nothing. The fallback on any machine that is not macOS |

## Where these words came from

The layer names, the flow vocabulary and the ViewModel are borrowed
deliberately from Android: `StateFlow` is an imitation of
`kotlinx.coroutines.StateFlow`, and the `ui` / `presentation` / `domain` /
`data` split is the layering that goes with it. If those words already mean
something to you, they mean the same thing here —
[the architecture document](ARCHITECTURE.md) says where each of them lives, and
[the flow lesson](lessons/flow_py.md) says how far the imitation goes.
