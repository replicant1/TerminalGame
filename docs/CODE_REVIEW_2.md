# Code review, second pass — the `terminalgame` package

A second look at the same source, made after
[the first review](CODE_REVIEW.md) and deliberately aimed at where that one did
not go: the two files it declared clean, the input path it never exercised, and
the text the game puts on the screen. Everything here is new — none of it
appears in the first document.

- **Reviewed:** [`terminalgame/`](../terminalgame) as it stands at commit
  `0c702ef`, 2 September 2026. Line numbers are as of that commit, so they
  have drifted where a fix has landed since.
- **Status:** as of `d1af551`, 3 September 2026. Four of the seven are fixed.
  The findings themselves are left as they were written -- this is a review
  with its outcome recorded against it, not a review rewritten to match what
  happened next.
- **Method:** where the first pass read, this one ran. Six of the seven
  findings were reproduced by executing the code — in a pty for the terminal
  ones, and against the real classes for the rest.

| Label | What it means |
|---|---|
| **Reproduced** | Run, and the wrong behaviour observed |
| **Reasoned** | Read closely and the reasoning checked, but not executed |

## Summary

| # | Finding | File | Kind | Verified | Status |
|---|---|---|---|---|---|
| 1 | Any unrecognised escape sequence quits the game | `app/main.py:40` | Correctness | Reproduced | [Fixed](https://github.com/replicant1/TerminalGame/pull/41) |
| 2 | Winning the game says "GAME OVER" | `presentation/view_model.py:426` | Ambiguity | Reproduced | [Fixed](https://github.com/replicant1/TerminalGame/pull/42) |
| 3 | `poll()` ignores a `stop()` made from inside a tick | `util/clock.py:76` | Correctness | Reproduced | [Fixed](https://github.com/replicant1/TerminalGame/pull/43) |
| 4 | `emit` delivers out of order under re-entrancy | `util/flow.py:70` | Correctness | Reproduced | Open |
| 5 | `close()` cannot restore the terminals that need it most | `ui/screen.py:137` | Correctness | Reproduced | [Fixed](https://github.com/replicant1/TerminalGame/pull/33) |
| 6 | A startup timeout deletes the sentinel under a live child | `app/launcher.py:260` | Correctness | Reasoned | Open |
| 7 | The conflation the design leans on never fires | `presentation/state.py:92` | Ambiguity | Reproduced | Open |

---

## 1. Any unrecognised escape sequence quits the game

`app/main.py:40` — **reproduced.**

**Fixed** — [#41](https://github.com/replicant1/TerminalGame/pull/41), commit `be1dca9`. 27 was dropped from `_QUIT_KEYS`; Esc no longer quits at all.

```python
_QUIT_KEYS = {ord("q"), ord("Q"), 27}  # 27 = Esc
```

Esc is a quit key, and ncurses hands back a bare `27` for the first byte of any
escape sequence its terminfo cannot decode. So the quit key is not really Esc —
it is *anything the terminal sends that curses does not recognise*.

Sent to a running game in a 30x40 pty:

| Sent | Result |
|---|---|
| `ESC O A` — arrow, application cursor mode | still running |
| `ESC [ A` — arrow, normal cursor mode | **game exited** |
| `ESC f` — Alt-f, or Option-f with Option-as-Meta | **game exited** |
| `ESC [ 200 ~` — bracketed-paste marker | **game exited** |
| `z` | still running |

Real triggers: Option-as-Meta in Terminal.app, a paste into the window, a mouse
report, or any mismatch between the terminal's cursor-key mode and the mode
`keypad(True)` asked for. The game ends instantly, with no confirmation and no
way back — a lost session for a stray keystroke.

The project already knows the mechanism: the `run-terminalgame` driver's own
notes call it a gotcha and send `ESC O A` for that reason. The game itself
still treats a bare 27 as an unambiguous instruction to quit.

**Fix.** Drop 27 from `_QUIT_KEYS` — `q` and `Q` are already there and are what
the status line advertises. If Esc must stay, distinguish a real one: read
again immediately after a 27 and treat it as Esc only when nothing follows
within a few milliseconds, which is what `ESCDELAY` exists for.

## 2. Winning the game says "GAME OVER"

`presentation/view_model.py:426` — **reproduced.**

**Fixed** — [#42](https://github.com/replicant1/TerminalGame/pull/42), commit `c179334`.

```
cleared: ' GAME OVER  score 0    q quits'
caught:  ' CAUGHT  score 0    q quits'
```

Losing gets the specific word. Winning gets the generic one, which reads like a
loss — the player who has just cleared the arena is told the game is over,
in the same words a defeat would use if the code had been written that way.

The docstring of that very method argues against it, twelve lines above the
line that does it (`:414`):

> A line reading GAME OVER after a ghost walked into somebody says what
> happened but not why, and the two endings are worth telling apart at a
> glance.

Every other name for that ending in the codebase agrees: the constant is
`_CLEARED = "cleared"`, the README says "the arena is cleared", and
`LIFECYCLE.md` calls the state Cleared. The one place a player ever sees it is
the one place it is called something else.

**Fix.** ` CLEARED  score {:<3}  q quits`, and the two endings then match the
shape the docstring describes.

## 3. `poll()` ignores a `stop()` made from inside a tick

`util/clock.py:76` — **reproduced.**

**Fixed** — [#43](https://github.com/replicant1/TerminalGame/pull/43), commit `4b26702`.

The loop tests only the deadline:

```python
while time.monotonic() >= self._next_deadline:
    self._next_deadline += self._interval
    fired += 1
    self._on_tick()
```

A callback that calls `stop()` is still called again for every other tick
already due. Measured with three ticks outstanding and the first callback
stopping the clock: **three ticks fired**, `running` False afterwards.

`stop`'s docstring says "Stops ticking. `poll` fires nothing until `start` is
called again", which is true between polls and false within the one in flight.

Not reachable today — `GameViewModel.tick` never stops the clock — but it is
the natural way to write "end the game on this tick", and the guarantee reads
as though it would hold.

**Fix.** `while self._running and time.monotonic() >= self._next_deadline:`.

## 4. `emit` delivers out of order under re-entrancy

`util/flow.py:70` — **reproduced.**

```python
self._value = new_value
for subscriber in list(self._subscribers):
    subscriber(new_value)
```

If a subscriber emits while delivery is in flight, the inner emit runs to
completion first — updating the value and notifying everyone — and then the
outer loop carries on handing the *older* value to the subscribers it had not
reached yet.

Two subscribers, A and B, where A emits `2` on seeing `1`:

```
A saw [0, 1, 2]      B saw [0, 2, 1]      flow.value == 2
```

B ends up holding 1 for good, while the flow holds 2 and will never mention it
again. The class documents kotlinx `StateFlow` semantics, which cannot leave a
collector stale like this.

Latent: `GameScreen.render` is the only subscriber and it never emits. It is
the sort of thing that stops being latent the moment a second subscriber is
added — which the class is explicitly built to allow.

**Fix.** Deliver the value that was current when the loop started and let a
re-entrant emit queue behind it, or refuse re-entrancy outright with a flag.

## 5. `close()` cannot restore the terminals that need it most

`ui/screen.py:137` — **reproduced.**

**Fixed** — [#33](https://github.com/replicant1/TerminalGame/pull/33), commit `8853d90`. Fixed alongside finding 1 of the first review, which is the same method pair and the same terminals.

`close()` restores the terminal in this order: `curs_set(1)`, `keypad(False)`,
`nocbreak()`, `echo()`, and finally `endwin()` at `:141`. The first of those
raises on exactly the terminals where it matters:

```
TERM=vt100   curs_set(0) -> RAISES     curs_set(1) -> RAISES
TERM=dumb    curs_set(0) -> RAISES     curs_set(1) -> RAISES
```

So on a terminal without `civis`/`cnorm`, `close()` dies on its first statement
and `endwin()` never runs — the same outcome as never calling it.

**This changes the repair for the first review's finding 1.** That finding
recommended wrapping `open()` and calling `self.close()` when it fails. On the
terminal that provokes the failure, `close()` would raise in turn and the
terminal would still be left in cbreak with echo off. The two findings have to
be fixed together.

**Fix.** Put `endwin()` in a `finally`, or run it first — it is the call that
actually gives the terminal back, and the cosmetic ones should not be able to
skip it. Guarding `curs_set` with `try/except curses.error` is the smaller
version of the same idea.

## 6. A startup timeout deletes the sentinel under a live child

`app/launcher.py:260` — **reasoned.**

If the child does not announce itself within `STARTUP_TIMEOUT_SECONDS`,
`_wait_for_child` raises `LaunchError`, and `launch`'s `finally` runs
`_cleanup(directory, sentinel)` on the way out — unlinking the sentinel and
removing its directory.

Nothing establishes that the child is dead. A child that was merely slow — a
loaded machine, a cold interpreter, Terminal.app taking its time — then carries
on running the game in a window that nobody will ever close, writing its
progress to a path that no longer exists. The write fails silently, by design:
`_write_sentinel` swallows `OSError` on the grounds that "the launcher's
liveness check covers us", and by then there is no launcher left to check.

The user is left with an orphaned game window and a command that exited with an
error, and the two facts do not obviously belong together.

**Fix.** On the timeout path, close the window if the id is known, or say in
the error that a window may have opened anyway. Deleting the directory last is
not the problem; assuming nothing is still writing to it is.

## 7. The conflation the design leans on never fires

`presentation/state.py:92`, with `view_model.py:326` — **reproduced.**

Instrumenting `StateFlow.emit` through a real game — 300 ticks and 1,200 arrow
presses, walls included:

```
emit() published: 900     dropped as equal: 0
```

Never once. Two independent reasons, either of which is enough:

- **`_publish()` sits inside the `if`.** A press into a wall returns without
  building a frame at all (`view_model.py:326` is inside
  `if self._maze.is_open(row, col):`), so the comparison is never reached.
- **`ViewState.tick` is part of the frame's identity.** It is a field of the
  frozen dataclass, so it is a field of the generated `__eq__`, and it changes
  on every tick. No two frames on the tick path can compare equal, whatever
  else is true of them.

The scenario document has this exactly right — it reports "dropped, because
they were identical: 0" and marks the branch "unreached today".
[`ARCHITECTURE.md:90`](ARCHITECTURE.md) does not:

> every tick emits a whole frame, and `StateFlow.emit` drops it if it is equal
> to the last one, which is what keeps an idle game from writing to the
> terminal at all

What keeps an idle game quiet is the early return in `tick` when `_ending` is
set. The dropping never happens.

**Fix.** This is a claim to correct rather than code to change — the mechanism
is sound and worth keeping for the second subscriber it was built for. If the
drop is wanted on the tick path, `tick` has to come out of the equality, which
means out of the dataclass or in as a `field(compare=False)`.

---

## A correction to my own method

The first run of the input test reported that a plain up arrow quits the game.
That was the harness, not the code: `keypad(True)` sends `smkx`, which puts the
terminal into application cursor mode, so the arrow is `ESC O A` and the `ESC
[ A` I sent was an unrecognised sequence — finding 1 firing on my own test.
The corrected run is the table in finding 1, and it is also why that finding
should be believed: the same mechanism caught me out inside ten minutes of
holding it.

## How this was produced

- Findings 1 and 5: `pty.fork()` with the window size set to 30x40 by
  `TIOCSWINSZ`, running the real game or the real `GameScreen`, under
  `TERM=xterm-256color` and `TERM=vt100`.
- Findings 2, 3, 4 and 7: the real classes driven directly — a fake `time`
  module for the clock, two subscribers for the flow, and a monkeypatched
  `emit` counting outcomes over a played-out game.
- Finding 6: read, and traced through `launch`, `_wait_for_child`,
  `_write_sentinel` and `_cleanup`. Not executed, because provoking it means
  making the child slow rather than absent.

The first pass's thirteen findings are in [`CODE_REVIEW.md`](CODE_REVIEW.md)
and none of them are repeated here.

## What is left

**4** and **6** are the remaining correctness findings in either review: `emit`
delivering out of order under re-entrancy, and a startup timeout deleting the
sentinel under a live child. **7** is an ambiguity — the conflation the design
leans on never fires — and costs nothing while it stands.
