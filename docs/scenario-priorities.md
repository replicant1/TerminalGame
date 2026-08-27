# What the priorities mean

Every scenario document in this folder carries a priority on the line under its
headline. The priority is one of `HIGH`, `MEDIUM` or `LOW`.

A priority is not a score for how interesting the scenario is. It answers a
narrower question: **what stops working, and how often, if this piece of the
program is wrong.**

The answer depends on how the program is normally run, not on how the code
reads. This program is normally started with the plain command
`python3 -m terminalgame.app.main`. That command opens a separate window and
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

| Scenario | Priority |
|---|---|
| [The launcher opens the game in its own Terminal window](the-launcher-opens-the-game-in-its-own-terminal-window.md) | `MEDIUM` |
| [The first frame is painted when the screen subscribes to the view model](the-first-frame-is-painted-when-the-screen-subscribes-to-the-view-model.md) | `HIGH` |
| [A clock tick moves the ghost and repaints the screen](a-clock-tick-moves-the-ghost-and-repaints-the-screen.md) | `HIGH` |

## Scenarios not yet written

Each of these is a real collaboration in the program that no document covers
yet. They are listed in bold rather than linked, because a link to a document
that does not exist would be a broken link.

- **An arrow key moves the player and repaints the screen** — `HIGH`. The only
  way a player can change anything the game does.
- **A quit key ends the game and closes the window** — `MEDIUM`. Covers how the
  game tells the waiting launcher that it has finished, and how the window is
  then closed without the terminal program asking the player to confirm.
- **A terminal too small to hold the playfield is refused** — `LOW`. The
  failure path out of opening the screen.
- **An unchanged frame is dropped before it reaches the terminal** — `LOW`. The
  comparison that stops identical pictures being drawn twice.
