# Scenario index

Every scenario document in this folder, what it is worth, an order to read them
in, and the ones still to be written.

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
| [The ghost catches the player and the game ends](the-ghost-catches-the-player-and-the-game-ends.md) | `MEDIUM` |
| [The last pill is eaten and the game is over](the-last-pill-is-eaten-and-the-game-is-over.md) | `MEDIUM` |
| [A quit key ends the game and closes the window](a-quit-key-ends-the-game-and-closes-the-window.md) | `MEDIUM` |

## A reading order

The list above is in the order the program does things, which is not the order
that makes them easiest to learn. What follows is three laps of the same
circuit. Each lap is whole on its own: stop after any one of them and you will
have a complete picture of the program, just a smaller one than if you go round
again.

The times are the reading times, at the pace of somebody reading carefully
rather than skimming.

**Before the first lap, or at any point during it:**
[Class overview](../CLASS_OVERVIEW.md) — 9 minutes. Not a scenario. It is the map:
every class, every public member, and each class's own description of itself.
Read it whenever you want the shape of the thing rather than the story of a
moment, and come back to it between laps.

### Lap 1 — one frame, from cause to bytes

**41 minutes.** The three documents that describe the path every drawn picture
takes. Nothing here is optional and nothing here is unusual: this is the game
running normally.

| | Document | Priority | Time |
|---:|---|---|---:|
| 1 | [The first frame is painted when the screen subscribes to the view model](the-first-frame-is-painted-when-the-screen-subscribes-to-the-view-model.md) | `HIGH` | 14 min |
| 2 | [A clock tick moves the ghost and repaints the screen](a-clock-tick-moves-the-ghost-and-repaints-the-screen.md) | `HIGH` | 13 min |
| 3 | [An arrow key moves the player and repaints the screen](an-arrow-key-moves-the-player-and-repaints-the-screen.md) | `HIGH` | 14 min |

At the end of this lap you can follow any picture in the game from the thing
that caused it to the bytes that reach the terminal, and you will have met every
part of the program except the maze and the window. You will also have met the
rule the whole design turns on, which is that the part that knows what a key is
never learns what it means, and the part that knows what it means never learns
that a key exists.

Read them in this order rather than any other: the first one is where the
registration is made that the second and third both travel along.

### Lap 2 — what is in the picture, and what a player does to it

**45 minutes.** Where the arena comes from, how it is drawn, the only thing in
the game a player can change about it, and the two ways a game ends by itself.

| | Document | Priority | Time |
|---:|---|---|---:|
| 4 | [A maze is carved and then braided until it has no dead ends](a-maze-is-carved-and-then-braided-until-it-has-no-dead-ends.md) | `MEDIUM` | 11 min |
| 5 | [A wall cell chooses its box-drawing glyph from its neighbours](a-wall-cell-chooses-its-box-drawing-glyph-from-its-neighbours.md) | `LOW` | 8 min |
| 6 | [A pill is eaten and the score goes up](a-pill-is-eaten-and-the-score-goes-up.md) | `MEDIUM` | 9 min |
| 7 | [The ghost catches the player and the game ends](the-ghost-catches-the-player-and-the-game-ends.md) | `MEDIUM` | 8 min |
| 8 | [The last pill is eaten and the game is over](the-last-pill-is-eaten-and-the-game-is-over.md) | `MEDIUM` | 9 min |

The first two are a pair, and the pairing is the point: one makes a shape out
of open and closed cells knowing nothing about how it will look, and the other
turns that shape into lines knowing nothing about how it was made. The last
three are the arc of a game: the move a player makes a few hundred times, and
then the two ways that stop being possible — the ghost reaching them, or the
arena running out of pills. Read the endings together; they are the same
machinery reached from opposite ends, and the second describes the stopped
state both arrive at.

This lap assumes lap 1. The pill documents deliberately do not repeat the story
of a key press; they describe the step that was added to it.

### Lap 3 — the window it all happens in, and the ways it ends

**36 minutes.** Everything on either side of a game: how a window is made for
it, how it is given back, and what happens when it cannot be had at all.

| | Document | Priority | Time |
|---:|---|---|---:|
| 9 | [The launcher opens the game in its own Terminal window](the-launcher-opens-the-game-in-its-own-terminal-window.md) | `MEDIUM` | 13 min |
| 10 | [A quit key ends the game and closes the window](a-quit-key-ends-the-game-and-closes-the-window.md) | `MEDIUM` | 9 min |
| 11 | [A terminal too small to hold the playfield is refused](a-terminal-too-small-to-hold-the-playfield-is-refused.md) | `LOW` | 7 min |
| 12 | [An unchanged frame is dropped before it reaches the terminal](an-unchanged-frame-is-dropped-before-it-reaches-the-terminal.md) | `LOW` | 7 min |

The first three are one story told at three moments: the window is opened, the
window is closed, and the window is refused. Read them together or not at all —
the second explains the arrangement the first sets up, and the third is the
first two with a failure in the middle.

The last one is deliberately last. It describes a comparison that, on the
program as it stands, never once says "identical", and the reason that is
interesting rather than pointless takes the other ten documents to appreciate.

## If you are here for one thing

| The question | The document |
|---|---|
| How does a key press become a moved character? | [An arrow key moves the player](an-arrow-key-moves-the-player-and-repaints-the-screen.md) |
| Why does the game not flicker? | [A clock tick moves the ghost](a-clock-tick-moves-the-ghost-and-repaints-the-screen.md), with the measurements |
| Where does the maze come from? | [A maze is carved and then braided](a-maze-is-carved-and-then-braided-until-it-has-no-dead-ends.md) |
| Why are the corners drawn correctly? | [A wall cell chooses its glyph](a-wall-cell-chooses-its-box-drawing-glyph-from-its-neighbours.md) |
| What is the score, and when does it change? | [A pill is eaten and the score goes up](a-pill-is-eaten-and-the-score-goes-up.md) |
| What happens if the ghost reaches me? | [The ghost catches the player](the-ghost-catches-the-player-and-the-game-ends.md) |
| What happens when the arena is empty? | [The last pill is eaten](the-last-pill-is-eaten-and-the-game-is-over.md) |
| Why does a window open, and why does it close by itself? | [The launcher opens the game](the-launcher-opens-the-game-in-its-own-terminal-window.md) and [A quit key ends the game](a-quit-key-ends-the-game-and-closes-the-window.md) |
| Why does it refuse to start in my terminal? | [A terminal too small](a-terminal-too-small-to-hold-the-playfield-is-refused.md) |

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
