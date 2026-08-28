---
name: run-terminalgame
description: Run, launch, drive, or screenshot the TerminalGame curses game — headlessly in a pty via .claude/skills/run-terminalgame/driver.py (send arrow keys, read frames back as text), or in its own Terminal.app window. Use when asked to run the game, start it, play it, check a change works in the real app, or capture what a frame looks like.
---

# Running TerminalGame

A `curses` game, stdlib only, system Python 3.9. Nothing to install, nothing to
build — but it paints a 30x40 terminal, so you cannot see it by reading stdout.

`driver.py` gives you a handle on it: a pty supplies the terminal, `pyte`
replays what curses writes into a character grid, and you send keys and print
frames back as text. That is the agent path — use it.

All paths below are relative to the project root (the directory holding
`terminalgame/`).

## Prerequisites

System Python 3.9 (`/usr/bin/python3`) is enough for the game. The driver also
needs `pyte`, which it installs for itself on first run into
`.claude/skills/run-terminalgame/.venv` and then re-execs — no action needed, it
just prints `driver: installing pyte into ...` once. Nothing is installed
system-wide; delete the `.venv` to reset.

There is no build step, no dependency install, and no test suite. The driver is
the check.

## Run (agent path)

Pipe commands to the driver, one per line:

```bash
./.claude/skills/run-terminalgame/driver.py <<'EOF'
show start
right 3
down 3
status
show after-moving
wait 1
quit
EOF
```

It starts the game, waits 1.5s for the first paint, runs the commands, and
exits with the game's exit code. Output goes to stdout — the boxed frames are
what the player would be looking at:

```
== after-moving ==
|╔═══════════════════════════╦═══════╗   |
|║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║   |
...
|║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║▐█▌▪ ▪ ▪ ▪ ║   |
|╚═══════════╩═══════════════════════╝   |
| tick 16     at 15,13 arrows, q quits   |
```

`▐█▌` is the player, `▗█▖` the ghost, `▪` a pill, `■` a fat pill. The right-hand
four columns are blank: the playfield is 36 columns wide inside a 40-column
terminal.

Commands:

| Command | Effect |
|---|---|
| `show [label]` | print the current 30x40 screen, boxed |
| `status` | print just the bottom row (`tick N  at row,col`) |
| `up`/`down`/`left`/`right [n]` | arrow key, n times (default 1) |
| `key <text>` | send literal characters, e.g. `key q` |
| `esc` | send Esc — **quits the game** |
| `wait <seconds>` | let the clock run (ticks are 0.15s) |
| `quit` | send `q`, wait for exit, print the exit code |

Every command settles for 0.6s afterwards so the ticks it caused have landed
before the next `show`. Raise `SETTLE` in the driver if a frame looks stale.

**Assert on the status line, not the maze.** The maze is carved randomly per
game and the ghost moves on its own, so no two runs match. `status` is the
stable readout: `at 15,13` is the player's cell, and it changes only in response
to your keys.

```bash
# did the arrow keys reach the game? try every direction -- any single one
# can be a no-op because the player is up against a wall
printf 'status\nright 2\nstatus\ndown 2\nstatus\nleft 2\nstatus\nup 2\nstatus\nquit\n' \
  | ./.claude/skills/run-terminalgame/driver.py
```

## Run (human path)

```bash
python3 -m terminalgame.app.main         # opens its own 30x40 Terminal.app window
python3 -m terminalgame.app.main --here  # runs in the current terminal
```

The default spawns a window through AppleScript, blocks until the game exits,
and forwards the exit code. Verified working: the window comes up at exactly
30 rows x 40 columns with custom title `Terminal Game`. Query it with:

```bash
/usr/bin/osascript -e 'tell application "Terminal"
  repeat with w in windows
    try
      set t to selected tab of w
      if custom title of t is "Terminal Game" then
        return "id=" & (id of w) & " rows=" & (number of rows of t) & " cols=" & (number of columns of t)
      end if
    end try
  end repeat
  return "NOT FOUND"
end tell'
# id=36475 rows=30 cols=40
```

To shut a spawned window down from a script, kill the game process — the
launcher notices, closes the window itself, and exits 0. Do **not** close the
window with AppleScript while the game runs; that is what the launcher's own
`busy` check avoids, and it puts a modal "terminate running process?" dialog on
the user's screen that blocks everything.

```bash
kill $(pgrep -f "terminalgame.app.main" | tail -1)   # two pids: launcher, then child
```

## Gotchas

* **Arrow keys must be sent in application cursor mode: `ESC O C`, not
  `ESC [ C`.** `keypad(True)` emits `smkx` at startup, after which ncurses only
  recognises the `SS3` form. Send the CSI form and ncurses hands the loop a bare
  `27`, which is in `_QUIT_KEYS` — so the game *silently exits on the first
  arrow press* and the next write to the pty fails with `EIO`. Looks exactly
  like a crash on input. The driver already sends the right form.
* **The pty must be 30x40 before the game measures it.** `GameScreen.open()`
  writes `ESC [ 8 ; 30 ; 40 t` asking the terminal to resize, which a pty
  ignores; it then measures and raises if the size is short:
  `Need at least 30x40 (rows x cols); terminal is 24x80.`, exit code 1. The
  driver sets the size with `TIOCSWINSZ` before the child can measure — the
  child blocks on a pipe until the parent says the size is in place, so the
  fork cannot race the measurement.
* **`LINES`/`COLUMNS` in your shell would break the driver, so it drops them.**
  ncurses prefers them over the pty's real size, so an exported `LINES=24`
  makes the game measure 24 rows in a 30-row pty and exit 1. The driver `pop`s
  both from the child's environment; before it did, running the driver from a
  shell that exported them failed every time.
* **`-m` only.** `python3 terminalgame/app/main.py` fails with
  `ImportError: attempted relative import with no known parent package`.
* **On macOS the pty master read returns EOF/`EIO` when the game exits**, before
  `waitpid` reports it. Treat it as "child gone and reap", not as an error — the
  driver does.
* **You cannot read the spawned window's screen over AppleScript.** `contents of
  <tab>` returns an object reference and `history of <tab>` returns the
  scrollback, which for a curses app is blank lines. Use the driver to inspect
  frames; the window query above is only good for size and title.
* **A move into a wall is a silent no-op** — the status line reads the same cell
  twice and nothing on screen changes. That is the game working, not the keys
  being dropped. Before concluding input is broken, try all four directions:
  in an unlucky spawn three of them are walls.
* **The game ignores SIGTERM.** ncurses installs its own handler at
  `initscr()` so it can restore the terminal, and the game sits straight
  through it — `ps` still reports `Ss+` seconds later. To stop it from a
  script, close the pty master (it notices the hangup within 0.1s) or send
  `q`, with SIGKILL as the backstop. `driver.py` cleans up that way on every
  exit path, including a malformed command, so nothing is left holding a pty.
* **`q`, `Q` and Esc all quit**, so `key q` in the middle of a script ends the
  run. Anything after it prints `driver: game already exited`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `driver: expected a repeat count, got 'foo'`, exit 1 | A malformed command (`right foo`, `wait x`, `right 0`). The script stops there and the game is shut down. |
| `driver: game already exited (0)` partway through a script | An Esc or a `q` reached the game — check for a CSI-form arrow key, or a stray `key q`. |
| Frames identical across two `show`s, tick not advancing | The game has exited; the emulator keeps the last frame. Add `status` after each key to catch it early. |
| `Need at least 30x40 ...`, exit 1 | Something other than the driver launched the game in a terminal shorter than 30x40. The driver sizes the pty before the child can measure it and strips `LINES`/`COLUMNS`, so it should not come from there. |
| `ImportError: attempted relative import` | Launched by path instead of `python3 -m terminalgame.app.main`. |
| First run stalls ~10s printing `installing pyte` | Expected once: it is building `.venv` and pip-installing `pyte`. Needs network. |
| `Terminal.app refused to open the window` | Automation permission for controlling Terminal was denied, or you are not on macOS. Use `--here`, or the driver. |
