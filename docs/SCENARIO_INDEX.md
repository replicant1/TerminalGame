# Scenario index

Every scenario document in this folder, what it is worth, and the ones still to
be written.

## What the priorities mean

Every scenario document in this folder carries a priority on the line under its
headline. The priority is one of `HIGH`, `MEDIUM` or `LOW`.

A priority is not a score for how interesting the scenario is. It answers a
narrower question: **what stops working, and how often, if this piece of the
program is wrong.**

The answer depends on how the program is normally run, not on how the code
reads. This program is normally started with the plain command
`python3 -m terminalgame.app.main`. That command opens a separate window, sized
to 30 rows by 40 columns and set to an 18 point font on a black background, and
plays the game inside it. There is a second way to start it, by adding the word
`--here`, which plays the game in the window the player is already using. The
second way is useful but it is not the ordinary way in, so work that only
happens on that path matters less.

| Priority | What earns it |
|---|---|
| `HIGH` | It happens on the path that **every drawn frame** takes, or it is the only route by which the game can be seen or controlled at all. If it is wrong there is either no picture or no way to change one |
| `MEDIUM` | It happens once for each run of the program, or only when the player presses a key, or only on a way of starting the program that is not the ordinary one. The picture survives without it, but the program is worse |
| `LOW` | It happens only when something has gone wrong, or only when an optional feature has been switched on |

## The scenarios in this folder

They are listed in the order the program does them: the maze before the window,
the window before the first picture, and the ending last.

| Scenario | Priority |
|---|---|
| [A maze is carved and then braided until it has no dead ends](a-maze-is-carved-and-then-braided-until-it-has-no-dead-ends.md) | `MEDIUM` |
| [A wall cell chooses its box-drawing glyph from its neighbours](a-wall-cell-chooses-its-box-drawing-glyph-from-its-neighbours.md) | `LOW` |
| [The launcher opens the game in its own Terminal window](the-launcher-opens-the-game-in-its-own-terminal-window.md) | `MEDIUM` |
| [A terminal too small to hold the playfield is refused](a-terminal-too-small-to-hold-the-playfield-is-refused.md) | `LOW` |
| [The first frame is painted when the screen subscribes to the view model](the-first-frame-is-painted-when-the-screen-subscribes-to-the-view-model.md) | `HIGH` |
| [A clock tick moves the ghost and repaints the screen](a-clock-tick-moves-the-ghost-and-repaints-the-screen.md) | `HIGH` |
| [An arrow key moves the player and repaints the screen](an-arrow-key-moves-the-player-and-repaints-the-screen.md) | `HIGH` |
| [A pill is eaten and the score goes up](a-pill-is-eaten-and-the-score-goes-up.md) | `MEDIUM` |
| [An unchanged frame is dropped before it reaches the terminal](an-unchanged-frame-is-dropped-before-it-reaches-the-terminal.md) | `LOW` |
| [The last pill is eaten and the game is over](the-last-pill-is-eaten-and-the-game-is-over.md) | `MEDIUM` |
| [A quit key ends the game and closes the window](a-quit-key-ends-the-game-and-closes-the-window.md) | `MEDIUM` |

## Scenarios not yet written

Each of these is a real collaboration in the program that no document covers
yet. They are listed in bold rather than linked, because a link to a document
that does not exist would be a broken link.

- **The game is played in the window the player is already using** — `LOW`.
  What `--here` does instead of opening a window, and why the request to resize
  the terminal is the only sizing there is on that path.
- **The clock catches up, or gives up, after the program is suspended** —
  `LOW`. What happens to the beat when a laptop is closed for an hour: the
  deadline is advanced by whole intervals so the rate cannot drift, and at most
  three missed beats are replayed before the clock realigns to the present.
- **The window is resized while a game is in progress** — `LOW`. The one key
  press that is neither a move nor a quit: the terminal reports its own resize
  as a key, and the screen re-measures and repaints from scratch rather than
  trusting what it believed was on the terminal.
- **The player and the ghost are placed at opposite ends of the maze** — `LOW`.
  Why neither can be given a fixed starting cell once the maze is random, and
  how "nearest to the middle" and "furthest from that" keep them apart whatever
  shape was carved.
