# Terminal Game — Functional Requirements

A simplified Pac-Man, played with the arrow keys in a small window of its own.
Each requirement carries a code so it can be referred to later.

## 1. The game

- **GAME-1** The player guides a single character around a walled maze, eating
  the dots laid along its corridors while one ghost roams the same maze.
- **GAME-2** The game is won by eating every dot, and lost by meeting the ghost.
- **GAME-3** There are no lives, levels, time limits, power-ups, pause or
  restart: one maze, one ghost, one outcome.

## 2. The window

- **WIN-1** The game opens in a window of its own, so it does not disturb
  whatever else the player has on screen.
- **WIN-2** The window is exactly 40 characters wide and 30 rows deep, in a
  fixed-width typeface large enough to read comfortably, on a black background.
- **WIN-3** The window is titled *Terminal Game*.
- **WIN-4** The window appears a little below and to the right of whatever
  window the player was last looking at, so it always lands somewhere visible.
- **WIN-5** The window closes by itself as soon as the game ends.

## 3. What is on the screen

- **SCRN-1** The top 29 rows show the maze; the bottom row is the status line.
- **SCRN-2** Everything is drawn from characters — there are no images.
- **SCRN-3** The walls are drawn as blue double lines that join up neatly with
  their neighbours into corners, tees and crossings; a wall square with no wall
  next to it is drawn as a single blue block.
- **SCRN-4** Each dot is a small dim gold square, one to a corridor square.
- **SCRN-5** The player is a bright yellow block, the ghost a pink block of a
  different shape, so the two can be told apart by colour and by outline.
- **SCRN-6** The status line is written in cyan.
- **SCRN-7** The picture is redrawn as things move, without flicker, and the
  text cursor is never visible.

A game in progress looks like this:

```
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
║ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪▐█▌▪ ▪ ▪ ▪ ▪ ║ ▪ ║   ← the player
║ ▪ ║ ▪ ║ ▪ ║ ▪ ════╗ ▪ ║ ▪ ╔═══╝ ▪ ║
║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║ ▪ ║ ▪ ▪ ▪ ║
║ ▪ ╔═══╩═══════╗ ▪ ║ ▪ ║ ▪ ║ ▪ ════╣
║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║ ▪ ║ ▪ ║ ▪ ▪ ▪ ║
║ ▪ ║ ▪ ║ ▪ ■ ▪ ║ ▪ ║ ▪ ║ ▪ ╚═══╗ ▪ ║   ← a lone wall square
║ ▪ ║ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ║ ▪ ╠════ ▪ ║ ▪ ╠═══════╗ ▪ ║ ▪ ║
║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║
╠═══════╝ ▪ ■ ▪ ║ ▪ ║ ▪ ║ ▪ ╠════ ▪ ║
║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║ ▪ ▪ ▪ ║ ▪ ║ ▪ ▪ ▪ ║
║ ▪ ╔═══════════╩═══════╝ ▪ ║ ▪ ║ ▪ ║
║ ▪ ║ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║ ▪ ║
║ ▪ ║ ▪ ═════════ ▪ ════════════╝ ▪ ║
║▗█▖▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ▪ ║   ← the ghost
╚═══════════════════════════════════╝
 score 0    arrows, q quits
```

## 4. The maze

- **MAZE-1** The maze is a grid 19 squares across and 29 squares deep, filling
  the window apart from a narrow blank margin down the right-hand edge.
- **MAZE-2** Each square of the grid is either corridor or wall; corridors are
  one square wide and run only north–south and east–west.
- **MAZE-3** A solid wall runs right around the outside, so nothing can leave
  the maze; there are no tunnels through the sides.
- **MAZE-4** A new maze is laid out at random every time the game is started,
  so no two games are the same.
- **MAZE-5** The maze has no dead ends: from any corridor square there are
  always at least two ways on, so the player is never trapped in a pocket.
- **MAZE-6** Every corridor square can be walked to from every other one, so no
  dot is unreachable.

## 5. Starting a game

- **START-1** The player begins on the corridor square nearest the middle of
  the maze.
- **START-2** The ghost begins on the corridor square furthest from the player,
  measured across the grid rather than along the corridors, so the two always
  start well apart.
- **START-3** Every corridor square holds one dot, except the square the player
  starts on, which is empty.
- **START-4** The score starts at zero.
- **START-5** The game is under way the moment the window opens: the ghost is
  already moving, and nothing has to be pressed to begin.

## 6. Controls

- **CTRL-1** The four arrow keys move the player one square up, down, left or
  right.
- **CTRL-2** The player moves one square per key press and then stops; holding
  a direction is not required and the player never drifts on their own.
- **CTRL-3** A press towards a wall does nothing at all.
- **CTRL-4** Pressing `q` (upper or lower case) quits at once, at any point in
  the game.
- **CTRL-5** No other key does anything, and nothing typed is echoed into the
  maze.

## 7. The ghost

- **GHOST-1** One ghost roams the maze, moving one square at a time about seven
  times a second, whether or not the player is moving.
- **GHOST-2** The ghost keeps going in a straight line for as long as the
  corridor lets it.
- **GHOST-3** Where it cannot carry on, it picks one of the other ways on at
  random, and turns back the way it came only when there is no other choice.
- **GHOST-4** The ghost does not hunt the player and takes no notice of where
  they are.

## 8. Dots and score

- **SCORE-1** Moving onto a square that still has a dot eats it, and the dot
  disappears from the maze for the rest of the game.
- **SCORE-2** Each dot eaten adds one to the score.
- **SCORE-3** Moving onto a square whose dot has already been eaten scores
  nothing.
- **SCORE-4** The ghost neither eats dots nor hides them; a dot under the ghost
  is still there to be taken.
- **SCORE-5** The score is shown in the status line and never goes down.

## 9. How a game ends

- **END-1** The game is lost the moment the player and the ghost stand on the
  same square, whether the player walked into the ghost or the ghost walked
  into the player.
- **END-2** The game is won when the last dot is eaten.
- **END-3** Eating the last dot on the square the ghost is standing on is a
  loss, not a win: meeting the ghost is decided first.
- **END-4** On a loss the ghost is drawn over the player, so the final picture
  shows what happened.
- **END-5** Once a game has ended everything stops: the ghost stands still, the
  arrow keys do nothing, and the last picture stays on screen.
- **END-6** `q` still quits, and is the only way to leave a finished game.

## 10. The status line

- **STAT-1** The bottom row of the window shows the score and the keys that can
  be used, and nothing else.
- **STAT-2** During play it reads `score 0    arrows, q quits`, with the score
  kept up to date.
- **STAT-3** On a loss it reads `CAUGHT  score 37   q quits`; on a win,
  `CLEARED  score 274  q quits` — so the line says which of the two endings
  happened, and what the final score was.
