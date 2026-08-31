# The test suite

256 tests over eight files, in plain `unittest`. The project has no
dependencies and the suite does not give it one.

Nobody should read all of it. Most of these tests exist so that when something
breaks, the failure names the fault — they are a reference, not a reading list.
This document is the reading list: **ten tests, about twelve minutes, and you
will have seen the whole game.** Everything after that is here for when you
need it.

Tests are named by class and method throughout rather than by line number, so
the links keep working when a file is edited.

## Running it

    python3 -m unittest discover -s tests -t .        # all 256, about 0.3s

Nothing here needs a terminal, a window, or a network. `osascript` is never
run, so the suite behaves the same on a machine with no Terminal.app.

    python3 -m unittest discover -s tests -t . -v     # every name and docstring

That second form is worth running once before reading anything. Every test is
named as a sentence and most carry a docstring saying why the behaviour is
worth having, so the output reads as a specification of the game — a few
hundred lines describing what the program promises, generated from the thing
that checks the promises are kept.

To narrow it down, name the module, the class, or the test:

    python3 -m unittest tests.test_maze
    python3 -m unittest tests.test_view_model.EndingTest
    python3 -m unittest tests.test_flow.StateFlowTest.test_emitting_an_equal_value_is_dropped

## Ten tests, and you have the game

In this order. Each one is the smallest statement of an idea the program is
built on, and together they cross every module.

| | Test | What it pins |
|---:|---|---|
| 1 | `test_flow.py` — `StateFlowTest.test_subscribing_delivers_the_current_value_at_once` | The registration every drawn frame travels along. A subscriber is handed the current value the moment it subscribes, which is why nothing ever has to ask for a frame |
| 2 | `test_screen.py` — `AttachTest.test_attaching_paints_the_first_frame_at_once` | The same idea from the other end: the screen subscribes, and the opening picture appears as a consequence rather than as a separate step |
| 3 | `test_main.py` — `GameLoopTest.test_an_arrow_key_moves_the_player` | A key press becoming a moved character, through the real loop. The one test that proves the loop runs at all |
| 4 | `test_view_model.py` — `PlayerMovementTest.test_the_pill_moved_onto_is_eaten_and_scored` | The move a player makes a few hundred times a game |
| 5 | `test_view_model.py` — `GhostMovementTest.test_a_tick_moves_the_ghost_exactly_one_cell` | The clock's half of the same story, and the reason the ghost reads as walking rather than teleporting |
| 6 | `test_maze.py` — `MazeGenerationTest.test_braiding_leaves_no_dead_ends` | What braiding is for, checked over four sizes and eight seeds. The ghost's movement rule depends on this being true |
| 7 | `test_view_model.py` — `WallGlyphTest.test_a_corner_joins_the_two_sides_it_has` | A wall cell picking its line from its neighbours — the whole glyph table in one assertion |
| 8 | `test_screen.py` — `RenderTest.test_the_gaps_in_a_layer_are_not_drawn_over_the_layer_beneath` | Why a frame carries two layers instead of one. A space is a character like any other, so only the runs are written |
| 9 | `test_view_model.py` — `EndingTest.test_a_capture_draws_the_ghost_on_top_of_the_player` | How the last frame of a lost game is told apart from any other frame |
| 10 | `test_flow.py` — `StateFlowTest.test_emitting_an_equal_value_is_dropped` | The comparison that keeps an unchanged frame off the terminal. Deliberately last: it is the least visible thing here and the easiest to appreciate once the other nine have been read |

Read 1 and 2 together, and 4 and 5 together. The rest stand alone.

## The scenarios, and the tests that pin them

[`docs/scenarios/`](../docs/scenarios/) describes what the program does; these
are the tests that check it still does it. Start from a scenario when you want
the story, and from its tests when you want to change something and find out
what you broke.

| Scenario | Where it is checked |
|---|---|
| [A maze is carved and then braided](../docs/scenarios/a-maze-is-carved-and-then-braided-until-it-has-no-dead-ends.md) | `test_maze.py` — `MazeGenerationTest`, all ten |
| [A wall cell chooses its glyph](../docs/scenarios/a-wall-cell-chooses-its-box-drawing-glyph-from-its-neighbours.md) | `test_view_model.py` — `WallGlyphTest`, and `LayerTest` for the result |
| [The launcher opens the game in its own window](../docs/scenarios/the-launcher-opens-the-game-in-its-own-terminal-window.md) | `test_launcher.py` — `CommandTest`, `SpawnTest`, `SentinelTest`, `WaitTest`, `LaunchTest` |
| [A terminal too small is refused](../docs/scenarios/a-terminal-too-small-to-hold-the-playfield-is-refused.md) | `test_screen.py` — `LifecycleTest.test_a_terminal_too_small_to_hold_the_playfield_is_refused`; `test_main.py` — `PlayTest.test_a_terminal_too_small_exits_one_and_says_why` |
| [The first frame is painted on subscribing](../docs/scenarios/the-first-frame-is-painted-when-the-screen-subscribes-to-the-view-model.md) | `test_screen.py` — `AttachTest`; `test_flow.py` — `StateFlowTest.test_subscribing_delivers_the_current_value_at_once` |
| [A clock tick moves the ghost](../docs/scenarios/a-clock-tick-moves-the-ghost-and-repaints-the-screen.md) | `test_view_model.py` — `GhostMovementTest`; `test_clock.py` — `GameClockTest`; `test_main.py` — `GameLoopTest.test_the_clock_is_polled_between_keys_so_the_ghost_moves` |
| [An arrow key moves the player](../docs/scenarios/an-arrow-key-moves-the-player-and-repaints-the-screen.md) | `test_view_model.py` — `PlayerMovementTest`; `test_main.py` — `GameLoopTest` |
| [A pill is eaten and the score goes up](../docs/scenarios/a-pill-is-eaten-and-the-score-goes-up.md) | `test_view_model.py` — `PlayerMovementTest`, and `NewGameTest.test_the_pill_under_the_player_is_taken_without_being_scored` |
| [An unchanged frame is dropped](../docs/scenarios/an-unchanged-frame-is-dropped-before-it-reaches-the-terminal.md) | `test_flow.py` — `StateFlowTest.test_emitting_an_equal_value_is_dropped`; `test_view_model.py` — `PlayerMovementTest.test_a_press_into_a_wall_publishes_nothing_at_all` |
| [The ghost catches the player](../docs/scenarios/the-ghost-catches-the-player-and-the-game-ends.md) | `test_view_model.py` — `EndingTest`, the first four |
| [The last pill is eaten](../docs/scenarios/the-last-pill-is-eaten-and-the-game-is-over.md) | `test_view_model.py` — `EndingTest`, the rest |
| [A quit key ends the game](../docs/scenarios/a-quit-key-ends-the-game-and-closes-the-window.md) | `test_main.py` — `GameLoopTest.test_q_ends_the_game`, `PlayTest`; `test_launcher.py` — `LaunchTest.test_the_window_is_closed_once_the_game_has_finished`; `test_screen.py` — `LifecycleTest.test_closing_gives_the_terminal_back` |

The scenario index lists four collaborations it has no document for yet. All
four have tests, so the behaviour is pinned even where the prose is missing:

| Scenario not yet written | Where it is checked anyway |
|---|---|
| The game is played in the window the player is already using | `test_main.py` — `ArgumentTest.test_here_keeps_the_game_in_this_terminal`, `MainTest.test_here_plays_in_this_terminal_instead_of_spawning` |
| The clock catches up, or gives up, after a suspension | `test_clock.py` — `GameClockTest.test_a_long_suspension_fires_at_most_the_catch_up_limit` and `..._resynchronises_instead_of_staying_behind` |
| The window is resized while a game is in progress | `test_main.py` — `GameLoopTest.test_a_resize_re_measures_and_repaints_the_current_frame`; `test_screen.py` — `AttachTest.test_a_resize_re_measures_and_repaints_from_scratch` |
| The player and the ghost are placed at opposite ends | `test_maze.py` — `MazePlacementTest.test_the_pair_never_place_two_things_on_one_cell`; `test_view_model.py` — `NewGameTest.test_the_two_do_not_start_on_the_same_cell` |

## The files, if you want the whole thing

In dependency order, which is also roughly easiest to hardest.

| File | Tests | Time | What it covers |
|---|---:|---:|---|
| [`test_flow.py`](test_flow.py) | 10 | 5 min | The pub/sub primitive: replay on subscribe, equal values dropped, a subscriber unsubscribing while being notified |
| [`test_state.py`](test_state.py) | 13 | 4 min | Frozen frames compared by value — the equality the dropping rests on |
| [`test_clock.py`](test_clock.py) | 13 | 5 min | Deadline arithmetic against a fake `time`: no drift, the catch-up cap, resynchronising |
| [`test_maze.py`](test_maze.py) | 43 | 10 min | The grid and its questions, then what generation promises, over four sizes and eight seeds |
| [`test_view_model.py`](test_view_model.py) | 59 | 18 min | The game: the glyph table, the two layers, movement, scoring, the ghost, both endings |
| [`test_screen.py`](test_screen.py) | 47 | 15 min | What reaches the terminal, and the curses lifetime, with no terminal attached |
| [`test_main.py`](test_main.py) | 29 | 10 min | The game loop driven for real, then the command line |
| [`test_launcher.py`](test_launcher.py) | 42 | 12 min | The shell line, the sentinel file, spawning and waiting — without `osascript` |
| [`fakes.py`](fakes.py) | — | 6 min | The three stand-ins the rest of the suite is built on |

## The fakes

[`fakes.py`](fakes.py) holds fakes rather than stubs: each behaves the way the
real thing does wherever that behaviour is part of what is being tested. That
matters more than it sounds. A stub is the author's belief about a collaborator
written down, so when the bug is in the collaborator the stub agrees with the
bug and the test passes.

- **`FakeWindow`** records what was drawn and *refuses a write that lands off
  the window*, exactly as curses does. Without that refusal a test could not
  tell a guard that clips from a guard that is not there.
- **`FakeCurses`** is the module minus the terminal, for opening and closing.
  Colour pairs are real bookkeeping, so a test can ask what colour a slot
  actually ended up with rather than which call was made.
- **`FakeScreen`** gives the game loop a scripted keyboard, and **raises rather
  than hangs** if the loop reads past its script. A suite that hangs is worse
  than one that goes red.

`GameScreen` itself is never faked. The drawing tests use the real class and
the real curses module with only `doupdate` held back, since laying characters
out needs no terminal behind it.

## How you know a test can fail

A test that cannot fail is a comment with a runtime cost. Every test here was
checked against a fault it should catch: forty-two faults were introduced one
at a time — braiding skipped, the clock's deadline reset instead of advanced,
the capture checked after the clear, the quit key ignored, the sentinel path
left unquoted — and forty of them turned the suite red.

Of the two that did not, one was a hollow test and was rewritten: `close()`
failing to unsubscribe stayed green because `render` also checks for a window,
so `AttachTest.test_closing_lets_go_of_the_state_flow` now reopens the screen
afterwards, which is the only thing that tells the two apart. The other is an
equivalent mutant — the bounds guard in `_put` is unobservable behind the
`try/except` around `addnstr` — and no test can distinguish it.

**If you add a test, do the same to it.** Break the line it covers, watch it go
red, read the message and check it names the real fault, then put the line
back. It costs about a minute and it is the only proof the test works.

## What the suite cannot tell you

It sees nothing outside the process. It cannot say whether the box-drawing
glyphs line up on a real terminal, whether the ghost's pink is actually
distinguishable from the player's yellow, or whether Terminal.app really opens
a window of the right size — only that the right numbers and characters were
handed over.

For those, run it and look:
[`.claude/skills/run-terminalgame`](../.claude/skills/run-terminalgame) drives
the game in a pty and reads frames back as text, and
[the tour from a Python prompt](../docs/REPL_TOUR.md) draws a frame in ten
lines with no terminal at all. A clean run of this suite is not a substitute
for either.
