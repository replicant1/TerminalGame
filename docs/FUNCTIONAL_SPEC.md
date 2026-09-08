# TerminalGame — Functional Specification

This document prescribes what the TerminalGame application **does**. It is a
functional specification, not documentation of the implementation: it describes
observable behaviour — what appears on the screen, what the keys do, what the
rules are, how it starts and finishes, and what it leaves behind when it
exits.

Individual classes are not specified. Behaviour that forms part of the system's
public interface is — the environment, the exit codes, and the extension point
for ghost behaviour.

**Scope of sources.** This specification is derived from the program's own
source, in the `terminalgame` folder, and from watching it run. Nothing else
informed it, and it points at nothing else.

### Conventions

**Normative and illustrative.** A numeric constant quoted in this document is
normative: a conforming implementation must produce that number, not merely
something like it. Three things are **illustrative** and are marked as such
where they appear — the sample frame in §[5.1](#51-a-sample-frame) and any
statement about what a particular seed produces (§[14.1](#141-seeding)).

**Indexing.** Character rows and columns are numbered **from zero**: the
playfield spans rows 0–29 and columns 0–39, and the status line is row 29. Cell
rows and columns are numbered from zero likewise. Where a count rather than an
index is meant the text says "30 rows", never "row 30".

**Requirement language.** *Shall* marks a requirement. *Is* and *does* describe
behaviour that follows from a requirement stated elsewhere.

**Sources.** Everything here comes from the program's own source and from
running it. Where the source does not settle a question, this document says so
rather than filling the gap from somewhere else.

Contents:

1. [The game](#1-the-game)
2. [Target platform](#2-target-platform)
3. [Screen geometry](#3-screen-geometry)
4. [The maze](#4-the-maze)
5. [What the screen looks like](#5-what-the-screen-looks-like)
6. [Colour](#6-colour)
7. [Rules of play](#7-rules-of-play)
8. [Timing](#8-timing)
9. [Input](#9-input)
10. [Rendering behaviour](#10-rendering-behaviour)
11. [Startup, failure and shutdown](#11-startup-failure-and-shutdown)
12. [Exit codes](#12-exit-codes)
13. [Environment](#13-environment)
14. [Determinism and the extension point](#14-determinism-and-the-extension-point)
15. [Prerequisites](#15-prerequisites)
16. [Constants, collected](#16-constants-collected)

---

## 1. The game

TerminalGame is a single-player, single-level, character-based maze game in the
Pac-Man tradition, drawn in a terminal window.

The player is a sprite that starts near the middle of a randomly generated
maze. Every corridor cell of the maze holds one pill. The player moves one cell
per arrow-key press and eats the pill on each cell it enters for the first
time, scoring one point per pill. A single ghost wanders the same maze on a
fixed clock, one cell per tick, and does not pursue the player.

A run of the game finishes in one of four ways:

| Ending | Cause | Result |
|---|---|---|
| **Refused** | The terminal could not be made large enough to hold the playfield | A message on stderr; the game never starts |
| **Cleared** | The player eats the last pill | Play stops; the status line reads `CLEARED` |
| **Caught** | The player and the ghost come to occupy the same cell | Play stops; the status line reads `CAUGHT`; the ghost is drawn on top of the player |
| **Quit** | The player presses `q` or `Q` (or interrupts with Ctrl-C) | The program exits and restores the terminal |

There is exactly one life and exactly one maze. A finished game (`CLEARED` or
`CAUGHT`) is frozen, not exited: nothing moves, no further frames are drawn,
the final frame stays on screen, and the only key that still has an effect is
the quit key. There is no restart, no pause, no level progression, no high
score table, and nothing is persisted between runs.

---

## 2. Target platform

The game should run on macOS. The default way of starting the game opens
a Terminal window of its own.

The application shall run with **nothing to install and nothing to build**.
It comes only in an English version, and there is no
dependency to fetch, no compilation step, no configuration file and no
generated code.

What the program does need, it needs from the terminal and the operating system.
The following are required, and are what the choice of technology implies:

* **Colour capability.** The maze walls are dark blue, the pills are brown, the ghost
is light blue and the pac-man is bright yellow.
* **Glyphs.** The
  playfield is drawn with double-line box-drawing characters
  (`║ ═ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬`), block elements (`█ ▐ ▌ ▗ ▖ ■`) and the small black
  square (`▪`).
* **Arrow keys.** The up, left, down and right arrow keys
are used to move the pac-man around the maze.
* **The terminal window.** The game exists within a fixed size terminal
window of its own.

**How the game is started is not a free choice.** It shall be launched by name,
which is what lets the program's parts locate one another. Pointing the language
runtime straight at the program's own file instead fails at once, before
anything is drawn.

---

## 3. Screen geometry

### 3.1 The playfield

The playfield is **30 character rows by 40 character columns** and fits exactly within
the terminal window.

The **last of the 30 rows is the status line**. The first 29 rows are the
arena.

### 3.2 Cells

The game reasons in **cells**, not characters. Positions, movement and
collisions are all counted in cells; the conversion to character coordinates
happens in exactly one place, when a frame is assembled.

**One cell is made up of 1 character row by 2 character columns.**

    one game cell
    ┌──────────────┬──────────────┐
    │  left        │  right       │   1 character row high
    │  character   │  character   │
    └──────────────┴──────────────┘
      char col x     char col x+1

This layout is chosen because using the default font, a 1x2 cell appears
very nearly square on screen.

The **left character of a cell is the centre line**. Everything that has to line
up with everything else — a wall's line, a pill, the middle of a sprite — sits
in the left hand character. The right character carries only a horizontal wall's
continuation eastwards, and is otherwise blank.

Two things are meant by *centre* here, and only one of them is about the cell.
A cell two characters wide has no middle character, so neither half is the
centre of anything. What the left characters form is a **centre line**: stack a
column of cells and their left characters line up into one unbroken column, and
that column is what everything aligns to. One of the two halves has to play that
part, because a cell two characters wide and one tall has no column *between*
its halves for a vertical wall to occupy. The left one was chosen. Where the
rest of this document needs to name a character it says **left** or **right**;
*centre line* means the alignment column and nothing else.

The division shows up plainly if the ink in a real frame is counted. Taking the
sample of §[5.1](#51-a-sample-frame) — a 29 by 19 maze, so 287 wall cells and
264 open ones:

| Layer | Ink in a **left** character | Ink in a **right** character |
|---|---|---|
| Walls | 287 — one for every wall cell, without exception | 122 — only those cells whose wall continues eastwards |
| Pills | 263 — one for every pill on the board | **0** |

The pill row is the one to take away: a pill never touches a right character at
all, in any maze. Its 263 is one short of the 264 open cells because the pill
under the player was taken during set-up
(§[7.2](#72-pills-and-scoring)). The wall row shows the single exception to the
rule and how partial it is — fewer than half the wall cells reach into their
right character, and those that do put nothing there but the `═` that joins them
to the cell next door.

Those counts are illustrative: another maze gives other totals. What does not
vary is the shape of the table — every wall cell and every pill in the left
column, and a zero in the bottom right.

### 3.3 Derived dimensions

| Quantity | Value | How it follows |
|---|---|---|
| Playfield | 30 rows × 40 cols | Fixed |
| Status line | 1 row (the last) | Fixed |
| Arena | 29 rows × 40 cols | 30 − 1 status row |
| Grid | 29 × 20 cells | 29 rows ÷ 1; 40 cols ÷ 2 |
| Maze | **29 × 19 cells** | The grid, reduced to an odd number of columns |
| Maze, in characters | 29 rows × 38 cols | 19 cells × 2 |
| Rightmost ink | character column 36 | The last cell's left character |
| Always blank | character columns 37, 38, 39 | The last cell's right character, plus the odd column dropped |

A maze must be an **odd** number of cells in each direction, because it needs a
wall cell on both sides of every junction. The grid's 20 columns are therefore
reduced to 19. The 29 rows are already odd and are used as they are.

---

## 4. The maze

### 4.1 Properties

A maze is a rectangular grid of cells, each either **wall** or **open
corridor**. A freshly generated maze shall satisfy all of the following:

* **Bordered.** The outermost cells on all four sides are wall.
* **Fully connected.** Every open cell is reachable from every other open cell
  by moving one cell at a time, north, south, west or east.
* **No dead ends.** Every open cell has at least two **open neighbours** — at
  least two of the four orthogonally adjacent cells are corridor. This is a
  guarantee, not an attempt.
* **Random.** A different maze is generated every run unless a seed is supplied.

The absence of dead ends is what makes the ghost's behaviour work: a ghost that
has just arrived somewhere always has a way on that is not the way it came, so
reversing is a last resort rather than the usual outcome. A run of the shipped
game should show zero reversals.

### 4.2 Generation

Maze generation occurs in two passes over a grid that begins with nothing but
wall.

**Junctions** are the cells whose row and column are both junction lines:

* the junction **rows** are the odd `r` with `1 ≤ r < rows − 1`;
* the junction **columns** are the odd `c` with `1 ≤ c < cols − 1`.

For an odd dimension that runs up to `rows − 2`, leaving a border one cell
thick; for an even one it stops at `rows − 3`, leaving a border two cells thick
down one side, which is why the maze is always given odd dimensions
(§[3.3](#33-derived-dimensions)). In the 29×19 maze the junction lines are rows
1–27 and columns 1–17: 14 junction rows, 9 junction columns, 126 junctions.

Junctions are two cells apart, so exactly one cell lies between any adjacent
pair, and that single cell is the only one either pass ever opens to join
them.

Those two rules sort every cell in the grid into one of three kinds, and the
pattern is easier seen than described. Here is a 9×9 maze *before* either pass
has run — nothing is open yet — with each cell marked by what may become of it:

          0 1 2 3 4 5 6 7 8
      0   # # # # # # # # #
      1   # J · J · J · J #
      2   # · # · # · # · #
      3   # J · J · J · J #
      4   # · # · # · # · #
      5   # J · J · J · J #
      6   # · # · # · # · #
      7   # J · J · J · J #
      8   # # # # # # # # #

| Mark | The cell | What becomes of it |
|---|---|---|
| `J` | A **junction**: odd row, odd column, inside the border | **Always** ends up open. Both passes move between these and nothing else |
| `·` | The one cell **between two junctions** | Open if a pass joined that pair, wall if not. Every choice either pass makes is a choice about one of these |
| `#` | The border, and every cell with an **even row and an even column** | **Never** opened. Each interior one sits with four junctions around it, and these are what the pillars and islands are made of |

Read a junction row across — row 1, say — and it alternates `J · J · J`: four
places to stand and three walls that may or may not be opened between them.
Read across an even row and the alternation is the other way round, `· # · # ·`:
the vertical joins, separated by cells that stay wall for the whole life of the
maze.

The real maze is 29 by 19 rather than 9 by 9, so the same three marks run to
rows 1–27 and columns 1–17 — 126 junctions — but the pattern does not change
with the size.

**Pass 1 — carve a perfect maze.** A depth-first walk over the junctions.

1. Choose a starting junction at random. **Open it**, and make it the sole
   entry on the stack. (Opening the start is easy to miss and leaves a
   one-cell hole in the middle of an otherwise correct maze if it is.)
2. Look at the junction on top of the stack. Collect the junctions two cells
   away — north, south, west, east — that are still closed.
3. If there are none, pop and go to 2.
4. Otherwise choose one at random, open **both** the single wall cell between
   the pair and the junction beyond it, push the new junction, and go to 2.
5. Stop when the stack is empty.

Every junction is reachable from every other through the junction lattice, so
the walk visits all of them and every junction ends up open. The result is a
*perfect* maze: exactly one route between any two cells — and therefore nothing
but dead ends, because every branch that is not the route to somewhere
terminates.

**Pass 2 — braid the dead ends away.** An **exit** of a junction, for this pass
only, is an *opened wall cell between that junction and an adjacent junction*.
A junction two cells from the border has fewer than four candidate exits,
because a neighbour off the junction lattice is not counted at all.

Sweep every open junction in turn:

* count its exits, and collect the still-closed ones;
* if it has **two or more** exits, leave it alone;
* if it has **fewer than two** and there is at least one closed candidate, pick
  one at random and open both that wall cell and the junction beyond it.

Repeat the whole sweep until a pass changes nothing. That terminates, and
terminates quickly, because opening a wall raises the exit count of two
junctions at once and never lowers one.

The test is "fewer than two", not "exactly one". After a carve every junction
already has at least one exit, so the two conditions coincide in practice — but
the pass is specified on the weaker test so that it is also correct on a grid
it did not carve itself.

Braiding deliberately destroys perfectness. The maze gains loops, and the wall
between two corridors that have just been joined stops being part of the border
and becomes part of an **island** — a region of wall entirely surrounded by
corridor. Islands hold no pills, because they hold no open cells.

**Minimum size.** Generation shall refuse a maze that has fewer than two
junction rows or fewer than two junction columns, because braiding could only
give such a maze a second exit by breaching the border. In practice this means
**at least 5 rows and 5 columns**.

### 4.3 Starting positions

* The **player** starts on the open cell nearest, by Manhattan distance, to the
  centre of **the grid** — not of the maze. The reference point is
  (grid rows ÷ 2, grid columns ÷ 2) rounded down, which for the 29×20
  grid is **(14, 10)**. The maze is one column narrower than the grid, so the
  maze's own centre column is 9: column 10 is what the rule gives and shall not
  be "corrected" to 9. The reference cell is itself usually wall, which is why
  the nearest open cell is used rather than the cell itself.
* The **ghost** starts on the open cell furthest from the player's starting
  cell, by Manhattan distance. Pairing "nearest to the middle" with "furthest
  from that" is what keeps the two from starting on top of each other whatever
  shape the maze took.
* Ties in either case are broken in reading order: top row first, and within a
  row, leftmost first.

---

## 5. What the screen looks like

### 5.1 A sample frame

**Illustrative, not normative.** This is the opening frame of one particular
game — the reference implementation's, from seed 7 — reproduced character for
character with the three always-blank right-hand columns trimmed. It shows what
a frame *looks like*. It is **not** a frame a conforming implementation is
obliged to produce from that seed, for the reason given in
§[14.1](#141-seeding).

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

29 rows of arena, one status line, 30 in all. `▐█▌` is the player, `▗█▖` the
ghost, `▪` a pill, and `■` a one-cell island of wall — there are two of them
here, at rows 18 and 22 (numbered from zero, as everywhere in this document).

This is the frame before anything has happened, so every corridor cell still
carries its pill except the one under the player, whose pill was taken during
set-up (§[7.2](#72-pills-and-scoring)) and which the sprite covers anyway. Once
play begins, **a corridor cell showing blank is one the player has already
walked**, and the trail of them is the score made visible.

### 5.2 The four things drawn, and their order

A frame is composed of exactly four things, drawn in this order, later ones
painting over earlier ones:

1. **The wall layer** — one character per position, blank wherever the pill
   layer has something.
2. **The pill layer** — blank wherever the wall layer has something.
3. **The sprites** — the player and the ghost, in an order that depends on the
   ending (§[7.5](#75-endings)).
4. **The status line** — the last row.

The maze arrives as two separate layers rather than one because a layer is drawn
in a single colour, and splitting them is what allows the pills to be a
different colour from the walls they sit between. Blank positions in a layer are
skipped rather than written: a space is a character like any other, and writing
one would paint over whatever an earlier pass put there.

### 5.3 Wall glyphs

A wall is drawn as a **line**, not a solid block, so each wall cell must choose
a glyph that joins the lines of its wall neighbours. Double lines are used
throughout: at this size they carry the weight a single-cell-thick wall with
pills either side of it needs.

For each wall cell, the four sides on which the *immediately adjacent cell is
also wall* are determined. **Out of bounds counts as not-wall**, which is what
closes the border into a rectangle instead of leaving it with arms pointing off
the playfield. The glyph placed in the cell's left character is then:

| Sides that are wall | Glyph | | Sides that are wall | Glyph |
|---|---|---|---|---|
| none | `■` | | N + E | `╚` |
| N *or* S *or* N+S | `║` | | N + W | `╝` |
| W *or* E *or* W+E | `═` | | S + E | `╔` |
| N + S + E | `╠` | | S + W | `╗` |
| N + S + W | `╣` | | N + W + E | `╩` |
| S + W + E | `╦` | | N + S + W + E | `╬` |

A cell with a single arm is drawn as the **through-line** rather than a stub,
because the double-line set has no half-lines to reach for. A cell with no wall
neighbours at all is a one-cell island — a pillar rather than a length of wall —
and is drawn as a filled square `■`, deliberately larger than a pill so the two
do not read as the same thing.

The cell's **right character** carries `═` if and only if the cell continues
eastwards into another wall, and a blank otherwise. Filling it in any other case
would leave the wall touching the pill in the next cell with none of the gap
every other wall cell leaves.

    a wall cell, two characters wide
    ┌───────────┬───────────┐
    │  glyph    │  ═ if the │
    │  from the │  wall goes│
    │  table    │  on east, │
    │           │  else ' ' │
    └───────────┴───────────┘

### 5.4 Pills

Every open cell carries **exactly one** pill — one dot, because one cell is one
place a sprite can stand, and two dots would say there were two. The pill is the
character `▪` placed in the cell's **left** character; the right character is
blank.

The glyph is a small square centred within its own character, so it sits
centred both across and down **on the centre line**. It is not centred within
the cell, and could not be: a cell has no middle character to be centred in,
which is the whole reason the centre line exists. A pill straddling the two
characters would land half a character to the right of that line, and a pill
drawn from half-height blocks would sit on the floor of the row while the
horizontal walls run through the middle of theirs.

Wall cells never carry a pill, so the solid islands braiding leaves behind come
out blank inside without anything having to go looking for them.

An eaten pill is replaced by a blank in the pill layer, permanently, for the
rest of the game.

### 5.5 Sprites

| Sprite | Art | Reads as |
|---|---|---|
| Player | `▐█▌` | A solid block, full height across all three characters' worth of ink |
| Ghost | `▗█▖` | A full-height middle with lower halves either side — narrower on top, wider at the foot |

Both are **three characters wide and one row tall**, and both are drawn
**centred on the cell's left character** — the centre line. The middle of the
art sits there, so the art's first character overhangs into the right character
of the cell before, and its last into the right character of its own cell. Both
of those are blank next to an open cell, since a wall carries its line eastwards
only when the next cell is also wall.

Sprite art shall be an **odd** number of characters wide. Ink centred on a
character's middle can be one character wide, or three, but never two: two
characters are centred on the join between them, half a character off the line
everything else sits on. Three characters with half blocks at the edges give two
characters' worth of ink — the full width of a corridor — while still being
centred. Sprite art shall also be exactly one row tall, matching the cell.

These constraints shall be checked **as the program loads** — before the
program has looked at how it was started, and before the terminal is touched —
and breaking one
shall stop the program outright rather than produce a drawing that looks very
slightly wrong. The failure therefore appears as a refusal to start, not as a
game that starts and then misdraws.

The player and the ghost are told apart by shape as well as by colour, so the
game remains playable on a terminal without colour.

### 5.6 The status line

The bottom row of the playfield. Its content depends on the state of the game
and takes one of exactly three forms:

| State | Exact layout, where `NNN` is the score left-aligned in three characters |
|---|---|
| Playing | `_score_NNN__arrows,_q_quits` |
| Caught | `_CAUGHT__score_NNN__q_quits` |
| Cleared | `_CLEARED__score_NNN__q_quits` |

`_` marks a space above. Written out for scores of 0, 7 and 263 respectively:

    " score 0    arrows, q quits"
    " CAUGHT  score 7    q quits"
    " CLEARED  score 263  q quits"

Each begins with one leading space, and the score occupies a left-aligned field
three characters wide followed by two spaces, so the text after it does not
shift as the score passes 9 and 99. The status line carries the score and the
keys, and nothing else. It does **not** carry the tick count or the player's
coordinates: those are readings for whoever is building the thing rather than
for anyone playing it, and a player reading their own coordinates off the bottom
of the screen is being told what the maze already shows them.

A finished game says **which** of the two ways it finished, in the same shape
either way — the word, the score, the key that leaves. A line reading
`GAME OVER` would say what happened but not why.

The budget for the line is **39 characters**, and that is the figure to design
to. It comes from the clipping rule in §[10.3](#103-clipping), which protects
the final cell of the **window's** last row: in a window exactly 30 rows tall
the status line *is* that row and loses its fortieth column, whereas in a taller
window it is not the last row and all 40 columns are in fact writable. Design to
39 and the line is correct in both.

No line comes near the limit — three digits hold the score for a maze this size,
which is a few hundred pills, and a fourth would still fit.

---

## 6. Colour

The application uses **logical colour slots**, mapped onto the terminal's
capabilities at start-up. The game logic never names a terminal colour.

| Slot | Applied to | 256-colour terminal | 8-colour terminal |
|---|---|---|---|
| Wall | The wall layer | Blue | Blue |
| Pill | The pill layer | Colour 136, a dim gold | Yellow, dim |
| Player | The player sprite | Colour 226, bright yellow | Yellow, bold |
| Ghost | The ghost sprite | Colour 213, bright pink | Red, bold |
| Status | The status line | Cyan | Cyan |

Rules:

* The terminal's **own background** is kept where the terminal supports a
  default background colour; black is used where it does not. A window the game
  opens for itself is given a black background explicitly.
* On a terminal reporting **no colour at all**, every slot draws in the default
  attribute and the game remains fully playable — the shapes distinguish
  everything that matters.
* **The player must be the only bright thing among the pills.** The player and
  the pills are both yellow, and the board is what the player has to be found
  against: a few hundred pills, one of them moving. Making the player merely
  brighter than the pills is not enough — two clear shades in a palette chart
  read as one more yellow square on the board. The pills are therefore pushed
  down to a dim gold, leaving the player the only bright thing among them.
* **The ghost's hue must be nowhere near the player's or the pills'**, so it is
  told apart at a glance rather than by shade. Pink is used rather than a
  brighter red for this reason, and it measures about 8.3:1 contrast against
  black where the terminal's own ANSI red manages 3.8.
* The 8-colour fallback asks the same gap of bold against dim, which depends on
  a setting the terminal owns — which is why it is the fallback and not the
  rule.

---

## 7. Rules of play

### 7.1 The player

* The player occupies exactly one cell.
* One arrow-key press moves the player exactly **one whole cell** in that
  direction. The player never lands straddling two cells.
* A press towards a wall cell, or off the edge of the maze, **does nothing at
  all**: the player does not move, no frame is published, and nothing on screen
  changes. This is a silent no-op, not an error.
* There is no per-tick player movement and no held-key repeat beyond whatever
  the terminal's own keyboard auto-repeat provides. **The player's speed is
  however fast they press.**
* Movement is orthogonal only. There is no diagonal move.

### 7.2 Pills and scoring

* On entering a cell, the player eats the pill there if one remains: the pill
  disappears from the board permanently and the score increases by **one**.
* Entering a cell whose pill has already been eaten changes the score and the
  board not at all. Only the sprite moves.
* **The score is therefore the count of distinct corridor cells the player has
  entered since the game began**, and it moves only in response to the player.
  The starting cell is not among them — the player never *enters* it — so a
  player who moves one cell and stops reads `score 1`, not 2.
* The player's starting cell is corridor and so begins with a pill. That pill is
  taken **silently, without scoring**, at the moment the game is set up. This is
  what makes the opening score `0` rather than `1`, and it stops a pill nobody
  can see from being the one the game is waiting on.
* The initial number of pills is therefore *(number of open cells) − 1*. For the
  seeded example in §[5.1](#51-a-sample-frame) that is 263 of 264.

### 7.3 The ghost

* There is exactly one ghost.
* The ghost moves **one cell per clock tick** and at no other time.
* The ghost does not eat pills and does not affect the score.
* The ghost's decision of where to go is made by a replaceable **ghost
  strategy** (§[14](#14-determinism-and-the-extension-point)). Each tick, the
  strategy is told the maze, the ghost's cell, the ghost's current heading, and
  the player's cell, and returns one step.
* **The move is validated, not trusted.** A step onto a wall cell is refused and
  the ghost stands still for that tick. A strategy with a bug in it therefore
  leaves the ghost standing still rather than inside a wall, where it would be
  drawn over the maze and could never be caught up with.
* The heading is updated **only when the ghost actually moves**, so a refused
  step leaves the strategy facing the way it was and free to choose again next
  tick.
* On the very first tick the ghost is given an **east** heading it never
  actually took, which may well point straight at a wall. A strategy must cope
  with that rather than trust the heading.

### 7.4 The shipped ghost strategy

The ghost the game ships with **carries straight on where it can and turns at
random where it cannot**. It does not hunt: it is handed the player's cell every
tick and does nothing with it.

Precisely:

1. If the cell in the current heading is open, return that heading.
2. Otherwise, collect the open steps that are not the reverse of the heading, in
   the fixed order north, south, west, east, and return one chosen uniformly at
   random.
3. If there is no such step at all, return the reverse of the heading.

Because the maze is braided and so has no dead ends, step 3 is unreachable in
normal play from any cell the ghost arrived at by moving. Reversing is a last
resort, not the usual outcome, and a full run should show zero reversals.

### 7.5 Endings

**Capture.** The player and the ghost are considered to have collided when they
occupy **the same cell** — a cell, not a character position. The two sprites
overlap on screen whenever they are within a character of each other, but only
one cell holds them both.

A capture may happen at either of two moments, and shall be checked after both:

* the ghost walking onto the player, on a tick;
* the player walking onto the ghost, on a key press.

There is no need to check for the two swapping places, which is the usual way a
collision check is fooled. Nothing moves at the same time as anything else — the
ghost moves on a tick and the player on a key press, one after another on one
thread — so a pass-through would take two moves and the check runs after each.

**Clearing.** Taking the last pill ends the game. This is checked on a key press
only, because the player is the only thing that eats.

**Precedence.** Capture is checked **before** the pill count. A player who takes
the last pill off the very cell the ghost is standing on has still walked into
the ghost, and the game is `CAUGHT`, not `CLEARED`.

**A finished game freezes.** Once either ending is set:

* ticks return immediately: the ghost stands still and the tick count stops;
* arrow keys do nothing;
* **no further frames are published**, so the last frame stays on the terminal
  at no cost at all — nothing is being redrawn;
* the status line of that final frame says which ending it was;
* on a capture, the **ghost is drawn on top of the player**. Normally the player
  is drawn last, which is what keeps it visible as the ghost passes; on a
  capture that would be exactly wrong, because the player would hide the thing
  that caught them and the final frame would look like any other.

Two inputs still do something. A quit key still quits, and **a resize
notification is still honoured**: the terminal is re-measured and the final
frame is repainted (§[10.4](#104-resize-during-play)), because the freeze is a
property of the game state and not of the screen. Everything else — arrow keys
included — is inert.

---

## 8. Timing

| Quantity | Value | What it is |
|---|---|---|
| Tick interval | **0.15 seconds** | The simulation step — roughly 1/7 second, fast enough for the ghost to read as moving rather than teleporting |
| Input poll | **33 milliseconds** | The longest a key read may block before the clock is checked again |
| Maximum catch-up ticks | **3** | The most ticks that may fire from one poll |

The clock is a **fixed-timestep deadline polled by the main loop**. It shall not
run on a background thread.

* The first tick falls one whole interval after the game starts.
* The deadline advances by **whole intervals**, not by resetting to *now*, so
  the tick rate does not drift slower over a long session.
* If the process is suspended — Ctrl-Z, laptop sleep — the clock shall not try to
  replay hours of missed ticks. At most 3 ticks fire from one poll, after which
  the clock discards the remaining backlog and resynchronises to the present.

**The input poll interval is input latency, not the frame rate.** A key press is
acted on and rendered the moment it arrives, not on the next tick.

---

## 9. Input

Keys are read one at a time, with a bounded wait. Each iteration of the main
loop reads at most one key and then polls the clock.

| Key | Effect |
|---|---|
| Up / Down / Left / Right arrow | Move the player one cell in that direction |
| `q`, `Q` | Quit immediately. The game exits and the terminal is restored |
| Terminal resize notification | Re-measure the terminal and repaint from scratch |
| Anything else | Ignored silently |

**Esc is deliberately not a quit key**, and shall not be made one. Whenever the
terminal sends an escape sequence the game's input layer cannot recognise, the
leading escape byte arrives on its own and the rest follows as ordinary
characters. That happens more often than it sounds: an arrow key sent in the
wrong cursor mode does it, so does a paste marker, so does Option-f on a
keyboard where Option is configured as Meta. Treating a lone escape as "quit"
would end the game on input the player never aimed at the game at all.

**Ctrl-C** terminates the run in exactly the same way as a quit key: the
terminal is restored on the way out and the exit code is 0.

Keys typed during play are not echoed onto the playfield, the caret is hidden,
and keys are delivered without waiting for Return.

---

## 10. Rendering behaviour

### 10.1 Whole frames, published on change

The game logic publishes **complete frames**. It never issues incremental draw
commands, and the screen never asks the game logic for anything: the screen
subscribes once at start-up and is pushed frames thereafter.

A frame is published when, and only when, something happens that could change
it: a tick, or a player move that was actually legal. A frame is **dropped
before it reaches the terminal if it matches the frame already showing**. A
frame is an unchangeable record and is compared by its contents, so the test
costs one comparison and no bookkeeping.

Frames also carry the **tick count** as part of their value, which makes two
otherwise identical frames distinguishable.

That last point has a consequence worth stating plainly, because it is
invisible from the requirement alone: **with these rules the drop never
actually fires.** Every tick increments the tick count before publishing, so no
two consecutive tick frames are ever equal; and a move that would change
nothing is refused before anything is published at all. The guard is therefore
a safety property: it makes a redundant publish free, and it keeps a later
change that publishes a frame speculatively from costing anything. It is not an
optimisation that earns its keep on every frame today — and it is required all
the same.

### 10.2 Full repaint, delta on the wire

Every layer of every frame is drawn in full into an off-screen copy of the
screen. What actually reaches the terminal is then worked out by comparing that
copy against what is believed to be on the terminal already: only the character
positions where the two differ are sent. Publishing whole frames therefore costs
no more terminal traffic than tracking the changes by hand would, and the rules
of the game are spared the bookkeeping entirely.

A steady frame — one in which only a sprite or two moved — goes out as a very
small write. A first paint, having nothing to compare against, goes out as a
large one. This document puts numbers on neither: they depend on the terminal
and on how the comparison is done, and the game controls neither.

Three properties shall be preserved, because they are what keeps the display
free of flicker and artifacts:

* **Blank the working copy; never declare the terminal unknown.** Both are one
  call away from each other, and they behave quite differently. Blanking the
  off-screen copy leaves the comparison intact, so only what really changed is
  sent. Declaring the terminal unknown throws that comparison away and forces a
  repaint from scratch — turning every frame into a first paint, which is
  exactly the flicker to be avoided.
* **One write to the terminal per frame**, not one per piece of the frame: the
  whole frame is composed off-screen and sent in a single update.
* **The caret is hidden, and parked** at the bottom-left corner, so nothing
  visibly chases the drawing across the screen.

### 10.3 Clipping

Drawing shall clip rather than fail:

* A row outside the window is not drawn.
* A run starting past the right edge is not drawn; one crossing it is truncated.
* A run starting at a negative column — which a sprite overhanging the left edge
  produces — is trimmed on the left rather than dropped whole.
* **The final character cell of the last row of the window is never written.**
  Writing it would scroll the window. This is why the status line's budget is 39
  characters and not 40.
* If the window is shorter than the playfield, only the rows that fit are drawn
  and the status line moves up to the last row that exists.

### 10.4 Resize during play

On being told the terminal has been resized, the game re-measures the terminal,
marks the screen for a full repaint, and immediately redraws the current frame.

* A window made **larger** is fine. The playfield stays 30×40 in the top-left
  and the surplus is left blank.
* A window made **smaller** mid-game is not treated as fatal. The frame is
  clipped to what fits (§[10.3](#103-clipping)) and play continues. The minimum
  size is enforced only at start-up.

---

## 11. Startup, failure and shutdown

### 11.1 Startup sequence

Whichever of the two modes is in use — a window the game opened for itself, or
the terminal it was started from — the game itself starts the same way:

1. The locale is initialised from the environment, which is required before any
   wide glyph is written.
2. The terminal is asked to resize itself to 30×40 by writing
   `ESC [ 8 ; 30 ; 40 t`, and **150 milliseconds** are allowed for the resize to
   land, because Terminal.app resizes asynchronously. Where the game opened the
   window itself this is a harmless no-op, the window already being the right
   size.
3. The terminal is taken over: keys delivered immediately and unechoed, caret
   hidden, arrow keys decoded, colours initialised.
4. The terminal is measured. If it is **shorter than 30 rows or narrower than 40
   columns**, startup fails (§[11.2](#112-the-terminal-is-too-small)).
5. The game state is created: a maze is carved and braided, the player and ghost
   are placed, and the first frame is built.
6. The screen subscribes to the game state, **and subscribing paints the first
   frame immediately**.
7. The input timeout is set and the clock is started.

### 11.2 The terminal is too small

If the terminal ignored the resize request and is still too small, the game
shall not start. A **single line** is written to standard error — it is shown
wrapped below only to fit this page — naming both the size required and the
size found, and saying that the terminal ignored the resize request and should
be resized by hand:

    Need at least 30x40 (rows x cols); terminal is 24x80. Your terminal ignored
    the resize request -- resize it by hand.

Sizes read *rows* × *columns*, in that order, on both halves of the message. The
exit code is 1.

**If the game is running inside a window opened for it**, the failure message
would vanish with the window, so the process shall additionally hold the window
open with the prompt `Press Return to close this window.` until Return is
pressed. End-of-input or an interrupt at that prompt is treated as Return.

### 11.3 Other start-up failures

Being too small is the failure the game *handles*. There is a second class it
does not, and an implementer needs to know it exists because the two behave
quite differently.

Taking over the terminal involves asking it to do several things a limited
terminal cannot. Hiding the caret is the one that bites: a terminal whose
description does not cover it
(§[2](#2-target-platform)) refuses, and the refusal is
fatal. Switching the arrow keys into decoded form, or setting up colour, can
fail the same way on a sufficiently threadbare description.

When that happens:

* the terminal is handed back first (§[11.4](#114-rollback-of-a-failed-start-up));
* the failure is **not** turned into a friendly message. It escapes unhandled,
  a diagnostic dump aimed at whoever is maintaining the program is written to
  standard error, and the process exits **1**;
* in a window opened for the game there is no "press Return" hold — that hold is
  specific to the too-small case — so the window closes and takes the
  diagnostic with it.
  The exit code 1 still reaches the terminal the command was typed into.

An implementation may improve on this by reporting such failures as tidily as
the too-small case. It shall not do worse: whatever happens, the terminal is
handed back and the exit code is non-zero.

### 11.4 Rollback of a failed start-up

Taking over the terminal is the first irreversible act. Anything that fails
*after* that point — including a terminal that cannot hide its caret, which is
exactly the sort of terminal that causes these failures — shall hand the
terminal back before the failure travels any further.

This matters because the terminal belongs to the user and outlives the process:
exiting alone does not undo the echo and line-discipline changes made when the
terminal was taken over.

### 11.5 Shutdown

On any exit — a quit key, Ctrl-C, an ending followed by a quit, a startup
failure, or an unhandled fault — the terminal shall be restored: caret visible,
echo on, line discipline back, arrow-key decoding off. Restoration shall be
attempted even on a terminal that refuses parts of the tidying up, and shall be
safe to perform twice.

---

## 12. Exit codes

| Code | Meaning |
|---|---|
| **0** | Normal exit: the player quit, or interrupted with Ctrl-C, or the window was closed from under the game |
| **1** | The terminal was too small; **or** the window could not be opened; **or** the game fell over with an unhandled fault |
| **2** | The game was asked to start in a way it did not understand |

Where the game opens a window of its own there are two processes, and the code
has to cross between them: the process that was started — the **launcher** —
opens the window and waits, while a second copy inside the window plays. They
communicate through a file the inner copy writes its progress to
(§[13](#13-environment)). Notes:

* Both endings *inside* the game — `CAUGHT` and `CLEARED` — exit 0. They are
  outcomes of play, not failures. Neither exits by itself; the player still
  presses a quit key.
* A crash shall never be reported to the launcher as success. The code written
  to that file defaults to 1 and is cleared to 0 only by an ending that actually
  reached one of the normal exits.
* The launcher forwards the inner copy's exit code unchanged, so the code the
  player's terminal sees is the game's own, and starting the game behaves like
  running any other blocking command.
* Failures on the launcher's own side — Terminal refusing to open a window, the
  window not starting within **20 seconds**, an unsupported platform — print a
  message on standard error and exit 1.

---

## 13. Environment

Two environment variables form part of the interface between the launcher and
the game process it starts. They are used **instead of** command-line arguments
because Terminal.app appends the running process's arguments to the window
title and that part of the title is not scriptable per tab: configured through
the environment, the title reads as the plain name of the program, with no
sentinel path trailing it.

| Variable | Set by | Meaning |
|---|---|---|
| `TERMINALGAME_CHILD` | The launcher, to `1` | This process is the copy running inside a window the launcher opened. It shall therefore play in place rather than open a window of its own, and it shall hold a fatal start-up error on screen (§[11.2](#112-the-terminal-is-too-small)) because the window is about to close. It is also the guard that makes a nested spawn refuse outright. |
| `TERMINALGAME_SENTINEL` | The launcher, to a path | The progress file this process reports `pid <n>` and `exit <code>` to. |

Both are read at start-up and neither is required. With no sentinel the process
reports its progress to nobody, which is the normal case for a game started by
hand. With no child variable set, and nothing else saying otherwise, a process
takes itself for a launcher and opens a window.

One further part of the environment is read explicitly. Before the terminal is
touched, the application **initialises the locale from the environment** — it
adopts whatever the environment specifies rather than the C default, which is
what allows the box-drawing and block glyphs of §[5](#5-what-the-screen-looks-like)
to be written. The environment shall therefore specify a locale whose encoding
can represent them; a UTF-8 locale does.

Beyond that, the application names no environment variable of its own. It uses
a terminal library that consults the environment for the terminal's description
and dimensions, but which variables those are, and how they interact, is that
library's business and is not fixed here.

---

## 14. Determinism and the extension point

### 14.1 Seeding

A game can be set up with an optional **seed** — a starting number for the
randomness. With no seed, every run gets a different maze and different turns. With one, a run is reproducible:
the same seed gives the same maze, the same two starting cells, and — as long as
no arrow key is pressed — the same ghost route, tick for tick. A seeded game is
the only kind an automated check can assert anything about.

The seed feeds **two separate sources of randomness, not one shared one**: one
is set up for carving the maze, another for the shipped ghost's turns, and both
are started from the same seed. Running them off a single source would make the
ghost's route depend on how many random choices the carving happened to need,
so a change to the maze rules would silently change the ghost's behaviour as
well. If a different ghost is supplied it brings its own randomness, if it
wants any, and the seed then reaches the maze alone.

**Reproducibility holds within one build of the game, not between different
ones.** This document fixes neither the method used to produce the random
numbers nor the order in which the two carving passes ask for them, so the same
seed will not give the same maze to someone who builds the game afresh from this
document — which is exactly why the sample in §[5.1](#51-a-sample-frame) is
marked illustrative. What is required is that a given build's output depend on
the seed and nothing else: same seed, same build, same maze, same two starting
cells, same ghost route. Matching mazes *between* builds would need the method
and the ordering pinned down too, and this document deliberately does not do
that.

**Nothing a player can do when starting the game reaches the seed.** Every game
played by an actual player is therefore unseeded, and so different from every
other.

### 14.2 Replacing the ghost

**How the ghost decides where to go is the one part of the game that is designed
to be swapped out**, and it is part of the public interface.

A ghost strategy is a replaceable part that answers exactly one question: shown
its surroundings, which single step should the ghost take? It holds none of the
game's own information and cannot move anything itself — it advises, and the
game decides whether to act on the advice (§[7.3](#73-the-ghost)).

The surroundings it is shown are one bundle of readings, which it may look at
but not alter:

| Reading | Meaning |
|---|---|
| **The maze** | The maze being played, so the ghost can ask which cells are open |
| **Where the ghost is** | Its cell — never a screen position. A ghost is never shown the screen |
| **Which way it is facing** | The step it took to arrive, which is what "carry straight on" means. On the very first tick this is a direction the ghost never actually travelled, and it may point straight at a wall |
| **Where the player is** | The player's cell, for a ghost that hunts |

One bundle rather than a fixed list of separate readings, because useful ghosts
do not all need the same things: the shipped one reads only the maze and its own
heading, a hunting ghost needs the player's cell as well, and one that keeps out
of another ghost's way would want something neither of them asks for. Adding a
reading to the bundle leaves every ghost already written still working.

Two more things are published alongside, because every ghost needs them and none
should have to write them out again:

* **The four steps a ghost may take** — north, south, west, east — in that
  fixed order. A ghost written later then breaks ties the same way the shipped
  one does, instead of behaving subtly differently because it happened to list
  the four in another order.
* **A "which ways may I go from here" enquiry.** Shown the surroundings, and
  optionally some steps to leave out, it reports which steps land on corridor,
  in the fixed order above. Leaving steps out is how a ghost refuses to double
  back. Every ghost has to begin by working out where it may legally go, so
  this is published rather than kept private to the shipped one.

Dropping in a different ghost shall require no change to the rules of the game.

### 14.3 What else is adjustable

These are settings rather than a stable interface — nothing outside the game
depends on them — but each has one prescribed home, and a change made anywhere
else is a change made in the wrong place:

| What | Where it is set |
|---|---|
| Tick rate; how long an input read may wait | Alongside the game loop |
| Playfield size; cell shape | Alongside the definition of a frame |
| How the maze is generated | Alongside the maze itself |
| The wall, pill and sprite characters | Alongside the code that builds a frame |
| Colours | Alongside the screen-painting code |
| Window title, font size, background colour | Alongside the window-opening code |

Two of these have consequences elsewhere. Changing the playfield size changes
the maze size and therefore the number of pills. Changing the cell shape
re-imposes the odd-width rule on the sprite characters, which is checked as the
program loads (§[5.5](#55-sprites)).

---

## 15. Prerequisites

### 15.1 What playing it needs

| Requirement | Detail |
|---|---|
| Operating system | **macOS** for the default way of starting, which is the only platform-specific part: it checks for macOS and for the system's AppleScript tool, and refuses on anything else. An in-place start names no operating system and needs none |
| Language runtime | Python 3. No particular release is required, and this document names none |
| Add-on software | **None.** Nothing to install, nothing to build, nothing to configure |
| Terminal | Terminal.app in windowed mode. In place, any terminal that can be sized to at least 30 rows by 40 columns, can emit UTF-8, and can be told to hide its caret. 256 colours are **preferred, not required** — the 8-colour and no-colour fallbacks of §[6](#6-colour) are conforming |
| Permissions | Permission to let the game control Terminal.app, for the default mode only. Refused permission produces the message `Terminal.app refused to open the window`, and the in-place start is the stated way round it |

The default mode's window is opened at **font size 18** on a **black
background**, offset 48 points down and right of whatever window was in front,
with the title **`Terminal Game`**. Rows and columns are counted in characters,
so a larger font grows the window in pixels and leaves the playfield exactly
30×40 — but raised far enough, the window will not fit the display, Terminal
will hand back fewer rows than were asked for, and the game will refuse to
start.

### 15.2 What checking it needs

Nothing beyond §[15.1](#151-what-playing-it-needs). Two properties of the
program make it checkable without a terminal at all, and both shall be
preserved:

* **The rules of the game know nothing about terminals.** The maze, the ghosts,
  the frames, the clock and the machinery that hands frames to the screen can
  all be built, driven and inspected on their own — no window, no game loop, no
  drawing.
* **Nothing reaches Terminal.app except through the window-opening step.** A
  check that never opens a window makes no AppleScript request, and so behaves
  the same on a machine with no Terminal.app at all.

What that leaves unchecked is the drawing itself, which needs a real terminal to
write into and something able to interpret terminal output to read back out.
This document does not prescribe how that is arranged.

---

## 16. Constants, collected

Every normative number in this specification, in one place.

All row and column numbers below are indexed from zero.

**Geometry**

| Constant | Value |
|---|---|
| Playfield rows | 30 |
| Playfield columns | 40 |
| Cell height, in character rows | 1 |
| Cell width, in character columns | 2 |
| Grid, in cells | 29 × 20 |
| Maze, in cells | 29 × 19 |
| Status line | Row 29, the last of the 30 |
| Status line character budget | 39 |
| Always-blank character columns | 37, 38, 39 |
| Minimum maze size | 5 × 5 cells |
| Sprite art | 3 characters wide, 1 row tall, odd width required |

**Timing**

| Constant | Value |
|---|---|
| Tick interval | 0.15 s |
| Input poll timeout | 33 ms |
| Maximum catch-up ticks per poll | 3 |
| Terminal resize settle | 150 ms |

**The window the game opens for itself**

| Constant | Value |
|---|---|
| Title | `Terminal Game` |
| Font size | 18 |
| Background | Black |
| Offset from the window that was in front | 48 points, down and right |
| How long the game inside it has to start | 20 s |

**Colour**

| Constant | Value |
|---|---|
| Player, 256-colour | 226 (bright yellow) |
| Pill, 256-colour | 136 (dim gold) |
| Ghost, 256-colour | 213 (bright pink) |
| Wall | Blue |
| Status | Cyan |
