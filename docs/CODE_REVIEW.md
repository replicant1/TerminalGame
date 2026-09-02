# Code review — the `terminalgame` package

A point-in-time review of the source, not part of the curated documentation
around it. Nothing here has been fixed; each finding says what it would take.

- **Reviewed:** every Python file under [`terminalgame/`](../terminalgame),
  2,207 lines across 13 files, as a body of code rather than as a diff.
- **Commit:** `0c702ef`, 2 September 2026. Line numbers are as of that commit.
- **Looked for:** correctness bugs, inefficiencies, ambiguities, and
  non-idiomatic Python — in that order of interest.

Every finding carries how far it was taken, because that is the difference
between a bug and a suspicion:

| Label | What it means |
|---|---|
| **Reproduced** | Run, and the wrong behaviour observed |
| **Confirmed in code** | Read closely and the reasoning checked, but not executed |
| **Reported** | Raised by the review pass and read but not independently exercised |

## Summary

| # | Finding | File | Kind | Verified |
|---|---|---|---|---|
| 1 | A crash after `initscr()` leaves the terminal unusable | `ui/screen.py:113` | Correctness | Reproduced |
| 2 | The launcher is told a crashed game succeeded | `app/main.py:91` | Correctness | Reproduced |
| 3 | `_braid` does not deliver the guarantee it documents | `presentation/maze.py:370` | Correctness | Reproduced |
| 4 | `_put` deletes a string instead of clipping it | `ui/screen.py:323` | Correctness | Confirmed in code |
| 5 | The maze is re-decomposed into runs every frame | `ui/screen.py:252` | Efficiency | Confirmed in code |
| 6 | The cell constants look parameterised but 1x2 is baked in | `presentation/view_model.py:150` | Ambiguity | Confirmed in code |
| 7 | O(n) membership tests in both inner loops | `presentation/maze.py:313, 352` | Efficiency | Confirmed in code |
| 8 | `attach` is silently not idempotent | `ui/screen.py:193` | Correctness | Confirmed in code |
| 9 | `launch` returns 0 for a game that never reported | `app/launcher.py:379` | Ambiguity | Reported |
| 10 | Rows built by `+=` on strings | `presentation/view_model.py:220` | Idiom | Confirmed in code |
| 11 | An undocumented two-column dead margin | `presentation/state.py:32` | Ambiguity | Reproduced |
| 12 | One midpoint, two spellings | `presentation/maze.py:331, 365` | Idiom | Confirmed in code |
| 13 | A re-export rule the only consumer does not follow | `presentation/__init__.py` | Ambiguity | Confirmed in code |

---

## 1. A crash after `initscr()` leaves the terminal unusable

`ui/screen.py:113` — **reproduced.**

`open()` takes the terminal over and then calls `curs_set(0)`, which raises
`curses.error` on any terminal whose terminfo lacks `civis`. The exception
escapes `open()`, so `__enter__` never returns, so `__exit__` never runs, so
`close()` never runs — and **`endwin()` is never called**. The terminal is left
in cbreak with echo off, which is a shell that no longer shows what you type
until you run `stty sane`.

```
$ TERM=vt100 python3 -m terminalgame.app.main --here
  File "terminalgame/ui/screen.py", line 113, in open
    curses.curs_set(0)
_curses.error: curs_set() returned ERR
```

Verified separately that `curs_set(0)` succeeds under `TERM=xterm-256color` and
raises under both `vt100` and `dumb`.

The author saw this window: six lines further down, the `TerminalTooSmall`
branch calls `self.close()` by hand before raising. Every statement between
`initscr()` and that check — `noecho`, `cbreak`, `curs_set`, `keypad`,
`_init_colors` — is outside that protection.

**Fix.** Wrap the body of `open()` from `initscr()` onwards in
`try: ... except BaseException: self.close(); raise`, and the hand-rolled
`self.close()` in the size check becomes redundant.

## 2. The launcher is told a crashed game succeeded

`app/main.py:91`, with the `finally` at `:105` — **reproduced.**

`play()` sets `exit_code = 0` before the `try`, and only the `TerminalTooSmall`
branch ever changes it. The `finally` writes
`launcher.announce_finished(sentinel, exit_code)` whatever happened, so any
other exception reports `exit 0` to the sentinel file, `_wait_for_child` reads
it, and `launch()` returns 0 to the shell.

**Failure.** Hit finding 1 — or any unexpected error — inside a spawned window,
and `python3 -m terminalgame.app.main && echo OK` prints `OK` after a
traceback. The one thing the sentinel exists to carry is the one thing it gets
wrong.

**Fix.** Add `except BaseException: exit_code = 1; raise`, or set
`exit_code = 1` up front and clear it to 0 only on the successful path. The
second is harder to get wrong later.

## 3. `_braid` does not deliver the guarantee it documents

`presentation/maze.py:370` — **reproduced.**

The braid gives up on a junction when it has one exit and no *closed junction
neighbour* to open: `if exits > 1 or not closed: continue`. That case arises
whenever the maze has only one junction row or one junction column, because the
terminal junctions of a single-file corridor have one junction neighbour each.

```
Maze.generate(r, c, seed=1).dead_ends()
  3x3 -> 1     3x5 -> 2     5x3 -> 2     3x7 -> 2
  5x5 -> 0     9x9 -> 0
```

`generate`'s docstring promises "a braided maze of that size, with a wall
border and no dead ends", and its `ValueError` advertises "at least three rows
and three columns" as the requirement. The true precondition is **five or more
in both dimensions**. `_braid`'s own docstring goes further and calls the
guarantee unconditional.

The shipped game is 29x19 and unaffected, but `GameViewModel._advance_ghost`
documents that it leans on the invariant, and the ghost page in `docs/` teaches
it as a property of the algorithm.

**Why the suite misses it.** `tests/test_maze.py` sweeps
`((9, 9), (11, 21), (29, 19), (5, 7))` — never below 5 — and
`test_the_smallest_maze_with_room_for_a_junction_is_allowed` asserts the 3x3
result *including* its dead end, so the gap is pinned as correct.

**Fix.** Either raise the `ValueError` threshold to 5 and correct both
docstrings, or extend the braid to open a wall towards the border for a
junction with no closed junction neighbour. The first matches what the code
does; the second matches what the docstrings claim.

## 4. `_put` deletes a string instead of clipping it

`ui/screen.py:323` — **confirmed in code.**

```python
if not (0 <= row < height) or col >= width:
    return
```

`col < 0` is never rejected. `limit = width - col` then exceeds the window,
`addnstr(row, -1, ...)` raises, and the `except curses.error: pass` at the
bottom swallows it — so the whole string vanishes rather than losing the
characters that fall outside. The docstring promises the opposite: "Writes text
at one position, clipping rather than raising."

**Latent, on three unasserted invariants.** A sprite's column is
`cell_col * CELL_COLS - len(art[0]) // 2`, cell column 0 is always border wall,
and sprites are the only caller that can go negative. Measured across 200
seeds, the lowest sprite column reached is 1.

**Fix.** Clip both ends: trim `text` by `-col` characters and set `col = 0`
when it is negative, the way the right edge is already handled.

## 5. The maze is re-decomposed into runs on every frame

`ui/screen.py:252` — **confirmed in code.**

`state.walls` is the same tuple object for the entire game — `self._walls` is
built once in `__init__` and never reassigned — and `state.pills` changes only
when a pill is eaten. `render` nevertheless calls `_put_runs` for all 58 layer
rows every frame, scanning every character in Python to rediscover run
boundaries that cannot have moved. The review pass measured ~2,200 characters
scanned and 428 `addnstr` calls per frame on seed 7; at seven ticks a second
plus a redraw per key press, that is a few thousand calls a second recomputing
a constant.

This is the only avoidable per-frame work in the package. Note that it costs
*Python* time, not terminal traffic — ncurses still diffs the back buffer, so
the wire stays quiet, which is presumably why it has never been felt.

**Fix.** Cache the `(row, col, text)` runs per layer, keyed on the layer
object's identity, and rebuild only when `_take_pill` replaces `_pills`.

## 6. The cell constants look parameterised but 1x2 is baked in

`presentation/view_model.py:150` — **confirmed in code.**

`_wall_cell`'s docstring says it "draws one wall cell as CELL_COLS characters";
the code returns exactly two, unconditionally:

```python
return _WALL_GLYPH[sides] + ("═" if sides & _EAST else " ")
```

Its neighbours `_PILL_CELL` and `_BLANK_CELL` genuinely are built from the
constants, so the file reads as though the cell size were a knob.

- Set `CELL_COLS = 3` and the wall rows come out one character short per cell
  while the pill rows do not, so the two layers desynchronise and the maze
  renders skewed.
- Set `CELL_ROWS = 2` and `_PILL_CELL` repeats the pill on both character rows
  of the cell — the very thing the `_PILL` comment says must not happen — while
  `_pills_left` counts pill *characters* (`:262`) and `_take_pill` blanks only
  the cell's first row and decrements by one. The count starts at twice the
  cell count and can never reach zero, so `_CLEARED` becomes unreachable and
  the only possible ending is a capture.

**Fix.** Cheapest is honesty: say in `state.py` that 1x2 is assumed, and fix
`_wall_cell`'s docstring to say two characters. Making the constants real means
touching `_wall_cell`, `_pills_left` and `_take_pill` together.

## 7. O(n) membership tests in both inner loops

`presentation/maze.py:313` and `:352` — **confirmed in code.**

Both `_carve` and `_braid` define `is_junction` as `row in junction_rows and
col in junction_cols`, where both are tuples, so each test is a linear scan;
`_braid` re-runs its full sweep until a pass changes nothing. `FrozenSet` is
already imported at the top of the file, and a set is also the plainer way to
say "is this one of the junction rows".

Small in absolute terms at 29x19, but it is needless super-linear work in the
one place with an unbounded outer loop.

## 8. `attach` is silently not idempotent

`ui/screen.py:193` — **confirmed in code.**

A second `attach` overwrites `self._unsubscribe` and orphans the first
subscription: `StateFlow.subscribe` appends unconditionally, so `render` is
then called twice per frame, and `close()` removes only one entry — `list.remove`
drops the first equal element — leaving a subscriber holding a closed screen
for the life of the flow.

`close`'s docstring explicitly promises "Safe to call twice". `attach` promises
nothing and quietly misbehaves. Not reachable from `main.run()`, which attaches
once.

**Fix.** Either unsubscribe first if already attached, or raise on a second
attach the way it already raises when the screen is not open.

## 9. `launch` returns 0 for a game that never reported

`app/launcher.py:379` — **reported.**

When the child's process disappears without writing `exit N`, `_wait_for_child`
returns `(0, None)` and `launch` hands that 0 to the shell. Its docstring says
"Returns: The game's exit code, so this behaves like an ordinary command" — but
there is no exit code in this case, and 0 reads as success. Close the game
window mid-play and the command reports success.

`_wait_for_child`'s own docstring documents the `None` pid for exactly this
case, so the behaviour is deliberate and it is `launch`'s docstring that has
drifted. Whether 0 is the right answer for "the window was closed from under
it" is a judgement call worth writing down either way.

## 10. Rows built by `+=` on strings

`presentation/view_model.py:220` — **confirmed in code.**

`wall_lines[i] += wall[i]` inside the column loop is quadratic in principle,
saved only by CPython's in-place `str` optimisation, which is an implementation
detail rather than a language guarantee. Collecting into a list and joining is
the plain idiom and is what the rest of the file reaches for. It runs once per
game, so this is readability rather than speed.

## 11. An undocumented two-column dead margin

`presentation/state.py:32` — **reproduced.**

`GRID_COLS = PLAYFIELD_COLS // CELL_COLS` is 20, and `_odd(20)` drops it to 19,
so the maze is 38 characters wide inside a 40-column playfield: every layer row
is exactly 38 characters. The rows work out exactly, because 29 is already odd,
so the asymmetry is horizontal only and invisible from the constants.

`_odd`'s docstring explains why the column is dropped, but nothing records that
the playfield is therefore flush left with a two-column gap on the right.

**Fix.** A comment, or `PLAYFIELD_COLS = 39`, which makes `GRID_COLS` 19 with
nothing wasted.

## 12. One midpoint, two spellings

`presentation/maze.py:331` and `:365` — **confirmed in code.**

```python
self._open[(row + next_row) // 2][(col + next_col) // 2] = True   # _carve
wall = (row + d_row // 2, col + d_col // 2)                       # _braid
```

Both are correct — the second only because `d_row` is exactly ±2, so
`d_row // 2` is exact — but a reader has to stop and confirm that `//` binds
tighter than `+`, and that the line is not the `(row + d_row) // 2` it
resembles. One spelling for one concept would cost nothing.

## 13. A re-export rule the only consumer does not follow

`presentation/__init__.py` — **confirmed in code.**

The module docstring says `state` is re-exported "so the UI depends on this
package, not on the module layout inside it". `ui/screen.py:24` imports
straight from `..presentation.state`, bypassing the re-export entirely. And
`COLOR_PILL` is missing from both the import list and `__all__`, though
`state.py` defines it and `screen.py` uses it — so the package's public colour
vocabulary is incomplete as well as unused.

**Fix.** Either point `screen.py` at the package and add `COLOR_PILL`, or drop
the claim from the docstring. The second is smaller and just as honest.

---

## Checked and found clean

- **`util/flow.py`** and **`util/clock.py`** — the deadline arithmetic, the
  catch-up cap and its realignment branch, the conflation fast path, and the
  subscriber-list copy in `emit` all hold up.
- **`presentation/maze.py`'s traversals** — `reachable_from`, `islands`,
  `dead_ends`, `nearest_open` and `farthest_open` are all O(rows x cols) with
  nothing quadratic hiding in them.
- **`app/main.py`** — the loop, the argument parsing and the environment
  fallback are sound, including the `VAR=1 exec ...` construct in
  `_build_command`, which does propagate the environment in sh, bash and zsh.
- The three `__init__.py` files, apart from finding 13.

## What to fix first

**1 and 2 together.** They compound: a terminal that cannot hide its cursor
wrecks the shell, and then the command reports success. Both are small, and a
test for each is easy — the suite already fakes curses.

**3 next**, as a docstring and a `ValueError` threshold rather than an
algorithm change, unless small mazes matter to you.

**5 if the game is ever felt to be slow**, which it is not today.

The rest are tidiness, and 9, 11 and 13 are each a sentence of documentation
rather than a code change.

## How this was produced

A review pass over the whole package, then independent verification of the
findings worth acting on: 1 and 2 reproduced by running the game under
`TERM=vt100` in a pty, 3 by generating small mazes and counting dead ends, 11
by measuring the built layers, and 4's reachability by taking the lowest sprite
column across 200 seeds. Findings labelled *confirmed in code* were read and
reasoned through but not executed; finding 9 is reported as it was raised.

The measurements in finding 5 are the review pass's, not re-run here.
