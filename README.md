# Terminal Game Skeleton

A retro, character-based game skeleton for macOS built on Python's stdlib `curses`.
No dependencies — the system Python 3.9 already ships everything needed.

    cd TerminalGame
    python3 -m terminalgame.app.main         # opens the game in its own 30x40 window
    python3 -m terminalgame.app.main --here  # runs in the current terminal instead

Arrows move, `q` or Esc quits. The maze is different every game.

## Structure

    terminalgame/
      app/
        main.py                    wiring + the main loop
        launcher.py                spawns the game's own Terminal window
      presentation/
        state.py                   ViewState     — one immutable frame
        maze.py                    Maze          — the carved playfield
        view_model.py              GameViewModel — game logic, owns the state
      ui/
        screen.py                  GameScreen    — curses rendering + keyboard
      util/
        clock.py                   GameClock     — fixed-timestep tick source
        flow.py                    StateFlow     — the pub/sub primitive

`presentation` imports from `util`; `ui` imports `ViewState` from
`presentation`; neither imports the other. `app` wires all three together and is
the only package that imports from every other one.

The game thinks in **cells**, not characters. A cell is one row by two columns,
which is very nearly square because a terminal character is about twice as tall
as it is wide. That makes a 30x40 window a playfield of 29 by 20 cells, and the
maze inside it 29 by 19 — a maze needs an odd number of cells across or its
border comes out two cells thick down one side.

There is no module to run by path — `main` uses relative imports, so it is
started as a module: `python3 -m terminalgame.app.main`.

Dependencies point one way:

    GameClock --tick()--> GameViewModel --StateFlow<ViewState>--> GameScreen

`GameViewModel` never imports curses; `GameScreen` never asks the ViewModel for
anything. The screen subscribes once at startup and is pushed complete frames.

## Full state or deltas?

**Publish the full ViewState. ncurses does the delta itself, and better.**

`refresh()`/`doupdate()` diffs the in-memory back buffer against what is
physically on the terminal and emits escape codes only for cells that actually
changed. Measured on this skeleton at 30x40:

    first paint      10657 bytes
    a tick           65-94 bytes
    an arrow key     67-94 bytes
    unchanged state      0 bytes

Every one of those ticks published a whole 30x40 ViewState. Hand-rolling deltas
in the ViewModel would add bookkeeping and could not beat that. The ranges are
colour: a frame that switches between the player's yellow, the pills' gold and
the ghost's pink costs a few bytes more than one that does not.

Three things keep it artifact-free, all in `screen.py`:

* `erase()`, never `clear()` — `clear()` sets a flag forcing a full repaint of
  the terminal on the next refresh, which is exactly the flicker to avoid.
* `noutrefresh()` + `doupdate()` — one atomic write per frame rather than one
  syscall burst per window.
* `curs_set(0)` plus parking the caret bottom-left — nothing tracks the draw
  position across the screen.

The fourth guard is in `flow.py`: `ViewState` is a frozen dataclass, so
`StateFlow.emit` compares by value and drops an unchanged frame before curses
is touched at all (the 0-byte row above).

## Threading

There is none, deliberately. `curses` is not thread-safe — a tick arriving on a
`threading.Timer` while the main thread is mid-refresh corrupts the display. So
`GameClock` is a monotonic deadline polled from the main loop, and `getch()` is
given a 33 ms timeout so input stays responsive between ticks. Tick handling
and rendering are therefore always ordered and always on one thread.

`GameClock` advances its deadline by whole intervals rather than resetting to
`now`, so the tick rate does not drift slower over a long session, and caps
catch-up at 3 ticks so a suspended process doesn't replay hours of backlog.

## Its own window

`python3 -m terminalgame.app.main` does not play in the terminal you typed it
into. It re-launches itself inside a fresh Terminal.app window and blocks until
the game exits, forwarding its exit code, so it still behaves like a normal
command.

Terminal.app's `tab` class exposes writable `number of rows` and `number of
columns`, so the window is created at exactly 30x40 rather than opened at the
default size and resized afterwards — there is no visible snap. The `tty`
property on the same tab is how the launcher identifies the window it just made
so it can close it again at the end.

Two things that are easy to get wrong here, both handled in `launcher.py`:

* **Don't close a window whose process is still alive.** The game writes its
  exit code to a sentinel file *before* the interpreter finishes unwinding. Ask
  Terminal to close the window in that gap and it puts up a "terminate running
  process?" modal, which blocks every subsequent AppleScript call. The launcher
  waits for the pid to actually disappear, and the close script checks `busy`
  as a second guard.
* **Never let the child spawn.** `launch()` refuses outright if
  `TERMINALGAME_CHILD=1` is already in its environment. Without that guard, any
  caller that fails to detect it is the spawned child opens another window,
  whose child opens another, and each generation is a real window on screen.
* **Terminal keeps closed windows in `every window` for a while**, as husks
  with zero tabs. Reading `selected tab` of one raises, which aborts the whole
  `repeat` loop before it reaches the window you care about. Every per-window
  access is wrapped in `try`.

The launcher watches a sentinel file rather than polling Terminal over
AppleScript, so a running game costs two `osascript` invocations in total. The
child records its pid there first, so if you close the window by hand the
launcher notices the process die instead of waiting forever.

The child is configured through environment variables (`TERMINALGAME_CHILD`,
`TERMINALGAME_SENTINEL`) rather than argv, because Terminal appends the running
process's arguments to the window title and that part is not scriptable. The
title reads `Terminal Game — Python -m terminalgame.app.main`, with no sentinel
path trailing it; the surrounding pieces come from global Terminal preferences
and are deliberately left alone.

### --here, and the escape-sequence fallback

`--here` plays in the current terminal. That path still needs to size the
window itself, so `GameScreen.open()` writes the xterm sequence
`ESC [ 8 ; 30 ; 40 t`, which Terminal.app and iTerm2 both honour, waits 150 ms
for the resize to land, then verifies with `getmaxyx()` and raises
`TerminalTooSmall` if the terminal ignored it. It runs on the spawned path too,
where it is a harmless no-op since the window is already the right size, and it
is what would size an iTerm2 window if you taught the launcher to use one.

A larger window is fine either way — the playfield stays 30x40 in the top-left.
`KEY_RESIZE` is handled mid-game.

## Tuning knobs

| What | Where |
|---|---|
| Tick rate (currently 0.15 s) | `TICK_INTERVAL_SECONDS` in `terminalgame/app/main.py` |
| Input latency | `INPUT_POLL_MILLISECONDS` in `terminalgame/app/main.py` |
| Playfield size | `PLAYFIELD_ROWS` / `PLAYFIELD_COLS` in `terminalgame/presentation/state.py` |
| Cell shape | `CELL_ROWS` / `CELL_COLS` in `terminalgame/presentation/state.py` |
| The maze | `Maze.generate()` in `terminalgame/presentation/maze.py` |
| Wall, pill and sprite glyphs | the constants at the top of `terminalgame/presentation/view_model.py` |
| Colours | `_init_colors()` in `terminalgame/ui/screen.py` |
| Window title, font size, background | `WINDOW_TITLE` / `FONT_SIZE` / `BACKGROUND_COLOR` in `terminalgame/app/launcher.py` |

## Next steps

Pills are drawn but not collected: the pill layer is built once and never
changes, so nothing is eaten, scored or counted. That is the obvious next
feature, and it is not free — the layer would move from a value built once to
state that changes as the game is played.

The maze is random rather than authored. A real Pac-Man maze is 28x31 cells,
which at one row by two columns per cell needs a 56 by 32 window rather than
this one's 40 by 30.

## Documentation

[`docs/`](docs/) holds a [class overview](docs/CLASS_OVERVIEW.md) and a set of
[scenarios](docs/SCENARIO_INDEX.md): one document per collaboration, each with a
sequence diagram and a step-by-step account of what passes between the parts.
