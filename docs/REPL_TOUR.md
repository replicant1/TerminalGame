# A tour of the code from a Python prompt

The game draws itself with curses, and curses wants a terminal it can take
over. That makes it an awkward thing to poke at. But the part of the program
that decides *what the picture is* never imports curses at all — that was the
point of splitting it — and it can all be driven from an ordinary Python
prompt with no window, no game loop and no clock.

This is a tour of the code by operating it rather than reading it. Every
snippet below was run, and every answer is the answer it actually gave. Start
from the project root:

```console
$ python3
```

Nothing here needs the game to be running, and nothing here can disturb a game
that is.

## 1. A maze on its own

[`Maze`](../terminalgame/presentation/maze.py#L31) knows nothing about
characters, colours or sprites, so it is the easiest thing in the program to
hold in your hand. Seed it and you get the same maze every time — the same one
the illustrations use.

```pycon
>>> from terminalgame.presentation.maze import Maze
>>> m = Maze.generate(11, 11, seed=7)
>>> m
Maze(11x11, 56 open cells)
>>> print("\n".join(m._to_rows()))
###########
#.........#
#.#.###.#.#
#.....#.#.#
#.#.#.#.#.#
#.#.....#.#
#.#######.#
#.........#
#.#.###.#.#
#.........#
###########
```

That is the whole maze: 121 cells, 56 of them corridor. Now ask it the two
things it promises, which are the reason the braiding pass exists at all:

```pycon
>>> m._dead_ends()
()
>>> m._is_fully_connected()
True
```

No corridor comes to a stop, and every corridor cell can be reached from every
other. The blocks of wall that the braiding cut off from the border are the
islands, and they are simply whatever was left over:

```pycon
>>> len(m._islands())
7
>>> m._islands()[0]
frozenset({(2, 2)})
```

Out of bounds counts as wall, which is what closes the border into a rectangle
rather than a fringe:

```pycon
>>> m.is_open(1, 1)
True
>>> m.is_open(0, 0)
False
>>> m.is_open(99, 99)
False
>>> m._open_neighbours(1, 1)
((2, 1), (1, 2))
```

You can also build one by hand, which is what
[`_from_rows`](../terminalgame/presentation/maze.py#L96) is for — a ring of
corridor around a single island:

```pycon
>>> tiny = Maze._from_rows(["#####",
...                        "#...#",
...                        "#.#.#",
...                        "#...#",
...                        "#####"])
>>> tiny._dead_ends()
()
>>> tiny._islands()
(frozenset({(2, 2)}),)
```

**Try changing:** the seed, and then the size. `Maze.generate(5, 5, seed=1)`
is small enough to check the braiding by eye. `Maze.generate(2, 2)` raises,
and the message says why.

## 2. The two layers

A maze becomes two layers of text, and the interesting property is that each
is blank wherever the other has something. That is what lets the screen draw
them in two passes and give the pills a different colour from the walls they
sit between.

```pycon
>>> from terminalgame.presentation import view_model as vm
>>> walls, pills = vm._to_layers(m)
>>> print("\n".join(walls))
╔═══════════════════╗
║                   ║
║   ■   ════╗   ║   ║
║           ║   ║   ║
║   ║   ■   ║   ║   ║
║   ║           ║   ║
║   ╚═══════════╝   ║
║                   ║
║   ■   ═════   ■   ║
║                   ║
╚═══════════════════╝
>>> print("\n".join(pills))

  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪
  ▪   ▪       ▪   ▪
  ▪ ▪ ▪ ▪ ▪   ▪   ▪
  ▪   ▪   ▪   ▪   ▪
  ▪   ▪ ▪ ▪ ▪ ▪   ▪
  ▪               ▪
  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪
  ▪   ▪       ▪   ▪
  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪

```

Hold the two printouts next to each other and the interlocking is obvious.
Look at one row on its own and the two-characters-per-cell rule is visible
too — a pill sits in the *left* character of its cell, and the right one is
the blank the wall's dash would otherwise fill:

```pycon
>>> walls[1]
'║                   ║ '
>>> pills[1]
'  ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪   '
```

Eleven cells, twenty-two characters.

## 3. A whole game, with no terminal

[`GameViewModel`](../terminalgame/presentation/view_model.py#L226) is the game.
Constructing one carves a maze, places the player and the ghost, and builds the
first frame — all before anything has been drawn anywhere.

```pycon
>>> from terminalgame.presentation.view_model import GameViewModel
>>> game = GameViewModel(seed=7)
>>> frame = game.state.value
>>> frame.status_line
' score 0    arrows, q quits'
>>> frame.tick
0
>>> len(frame.walls), len(frame.walls[0])
(29, 38)
>>> frame.sprites
(Sprite(row=27, col=1, art=('▗█▖',), color=3), Sprite(row=13, col=19, art=('▐█▌',), color=2))
```

Two things in that last answer are worth pausing on. The sprites are in
**character** coordinates, not cells — the conversion happens in one place and
the screen never learns that cells exist. And the arena is 38 characters wide
where the playfield is 40, because a maze needs an odd number of cells for its
border to come out one cell thick.

Now play, without a keyboard. A direction is a pair of numbers, and that is all
the game is ever told:

```pycon
>>> game.on_direction(0, 1)          # right
>>> game.state.value.status_line
' score 1    arrows, q quits'
>>> game.on_direction(0, -1)         # back to where it started
>>> game.state.value.status_line
' score 1    arrows, q quits'
```

The score went up once and then stayed. Walking back over a cell that has
already been cleared scores nothing, because the pill is gone — the whole of
that rule is one character comparison in
[`_take_pill`](../terminalgame/presentation/view_model.py#L327).

A move into wall is refused, and refused *before* anything is published:

```pycon
>>> before = game.state.value
>>> game.on_direction(-1, 0)         # up, into wall
>>> game.state.value is before
True
```

Not merely equal — the **same object**. No frame was built, so none was
offered, so the carrier had nothing to compare. That is the finding the
[unchanged-frame scenario](scenarios/an-unchanged-frame-is-dropped-before-it-reaches-the-terminal.md)
is about, and you have just reproduced it in three lines.

Frames cannot be altered after they are made:

```pycon
>>> before.tick = 99
Traceback (most recent call last):
  ...
dataclasses.FrozenInstanceError: cannot assign to field 'tick'
```

## 4. Drawing a frame yourself

Nothing above drew anything. A frame is two layers plus some sprites, and
flattening it is about ten lines — which is, minus the colours and the escape
codes, exactly what [`GameScreen`](../terminalgame/ui/screen.py#L59) does:

```python
def as_text(state):
    """Flattens a frame the way GameScreen paints it: layers first, sprites on top."""
    rows = [list(line) for line in state.walls]
    for r, line in enumerate(state.pills):
        for c, ch in enumerate(line):
            if ch != " ":
                rows[r][c] = ch
    for sprite in state.sprites:
        for i, line in enumerate(sprite.art):
            for j, ch in enumerate(line):
                rows[sprite.row + i][sprite.col + j] = ch
    return "\n".join("".join(row) for row in rows) + "\n" + state.status_line
```

Paste that in, and the game appears in your scrollback:

```pycon
>>> game = GameViewModel(seed=7)
>>> print(as_text(game.state.value))
╔═══════════════════════╦═══════════╗
║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║
║ ▪ ║ ▪ ╔═══════╦════ ▪ ║ ▪ ═════ ▪ ║
║ ▪ ║ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║
║ ▪ ║ ▪ ║ ▪ ║ ▪ ║ ▪ ════╣ ▪ ════╗ ▪ ║
║ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ║ ▪ ════╣ ▪ ╠════ ▪ ╠════ ▪ ║ ▪ ║
║ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ╠════ ▪ ║ ▪ ║ ▪ ╔═══╝ ▪ ════╝ ▪ ║
║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║
║ ▪ ║ ▪ ╔═══════╝ ▪ ║ ▪ ════════╗ ▪ ║
║ ▪ ║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ║ ▪ ║ ▪ ╔═══════╩════════ ▪ ║ ▪ ║
║ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪▐█▌▪ ▪ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ║ ▪ ║ ▪ ║ ▪ ════╗ ▪ ║ ▪ ╔═══╝ ▪ ║
║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║ ▪ ║ ▪ ▪ ▪ ║
║ ▪ ╔═══╩═══════╗ ▪ ║ ▪ ║ ▪ ║ ▪ ════╣
║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║ ▪ ║ ▪ ║ ▪ ▪ ▪ ║
║ ▪ ║ ▪ ║ ▪ ■ ▪ ║ ▪ ║ ▪ ║ ▪ ╚═══╗ ▪ ║
║ ▪ ║ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ║ ▪ ╠════ ▪ ║ ▪ ╠═══════╗ ▪ ║ ▪ ║
║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║
╠═══════╝ ▪ ■ ▪ ║ ▪ ║ ▪ ║ ▪ ╠════ ▪ ║
║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ║
║ ▪ ╔═══════════╩═══════╝ ▪ ║ ▪ ║ ▪ ║
║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ║ ▪ ═════════ ▪ ════════════╝ ▪ ║
║▗█▖▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║
╚═══════════════════════════════════╝
 score 0    arrows, q quits
```

Then walk, and watch the trail the eating leaves behind:

```pycon
>>> for _ in range(4):
...     game.on_direction(0, 1)
...
>>> print(as_text(game.state.value))
```

The four cells to the left of the player are blank now, and the readings line
says `score 4`. Two of the illustrated scenarios —
[a pill is eaten](scenarios/a-pill-is-eaten-and-the-score-goes-up.md) and
[a wall cell chooses its glyph](scenarios/a-wall-cell-chooses-its-box-drawing-glyph-from-its-neighbours.md)
— are about exactly what you are looking at.

## 5. The carrier, and the branch the game never reaches

[`StateFlow`](../terminalgame/util/flow.py#L13) holds one value and tells
subscribers when it changes. A new subscriber is handed the current value at
once, which is how the screen gets its first frame without asking for one:

```pycon
>>> from terminalgame.util.flow import StateFlow
>>> flow = StateFlow(1)
>>> seen = []
>>> stop = flow.subscribe(seen.append)
>>> seen
[1]
>>> flow.emit(2)
True
>>> seen
[1, 2]
```

Now emit the same value again:

```pycon
>>> flow.emit(2)
False
>>> seen
[1, 2]
```

`False`, and the subscriber was not called. **That branch is unreachable from
the game itself** — every path that could offer an unchanged frame returns
before building one — so the prompt is the only place it can be seen at all.
Unsubscribing works the same way, by calling what `subscribe` gave back:

```pycon
>>> stop()
>>> flow.emit(3)
True
>>> seen
[1, 2]
>>> flow.value
3
```

## 6. The clock

[`GameClock`](../terminalgame/util/clock.py#L13) runs nothing on its own. It is
a deadline that the main loop polls, which is what keeps every tick on the same
thread as the drawing.

```pycon
>>> import time
>>> from terminalgame.util.clock import GameClock
>>> beats = []
>>> clock = GameClock(0.05, lambda: beats.append(len(beats)))
>>> clock.running
False
>>> clock.start()
>>> clock.poll()
0
>>> time.sleep(0.12)
>>> clock.poll()
2
>>> beats
[0, 1]
```

Polling straight after `start` fires nothing, because the first beat is a whole
interval away. Polling after two and a bit intervals fires twice, catching up
by whole intervals so the rate does not drift slower over a long session — and
never more than `GameClock.MAX_CATCH_UP_TICKS` at a time, so a laptop waking
from sleep does not replay an hour of missed beats.

## Where to go next

- Wire it together yourself: `clock = GameClock(0.15, game.tick)`, then poll it
  in a loop and print `as_text(game.state.value)`. That is
  [`_run`](../terminalgame/app/main.py#L43) with the curses taken out.
- [The scenario index](scenarios/SCENARIO_INDEX.md) — the same material as
  stories, in a suggested reading order.
- [The class overview](CLASS_OVERVIEW.md) — every public member, with the
  docstring it was written with.
- The two step-through pages, for the parts that are easier watched than read:
  [carving and braiding](https://replicant1.github.io/TerminalGame/docs/step-by-step/maze-step-by-step.html) and
  [every wall cell picking its glyph](https://replicant1.github.io/TerminalGame/docs/step-by-step/wall-glyphs-step-by-step.html).

The one thing you cannot reach from here is
[`GameScreen`](../terminalgame/ui/screen.py#L59): importing it imports curses,
and opening it takes over the terminal you are typing into. That is the whole
of what the split buys — everything above ran without it.
