# Enough Python to read `clock.py`

For somebody fluent in Kotlin or Java. The file is
[`terminalgame/util/clock.py`](../../terminalgame/util/clock.py) and it is
eighty-five lines, most of which you can already read: it is a class, an
`__init__`, a `@property` and three short methods, all of which
[the `view_model.py` lesson](view_model_py.md) and
[the `flow.py` lesson](flow_py.md) have covered.

So this one is short on syntax and spends its length on the two things in the
file that are genuinely worth explaining. One is a Python mechanism you have
not met yet — how `import time` makes the clock swappable, which is why a test
can run a whole session in no time at all. The other is not Python but
arithmetic: why the deadline is advanced rather than reset, and why a JVM
reader's instinct for this file is wrong.

## What it is, in one paragraph

A tick source that does not run. It holds a deadline and a callback, and it
does nothing at all until somebody calls `poll()` — at which point it fires the
callback once for every whole interval that has gone by. The game loop polls it
between key presses. Nothing is scheduled, nothing sleeps, and there is no
second thread anywhere in the program.

## The one new piece of syntax

```python
class GameClock:
    MAX_CATCH_UP_TICKS = 3
```

An assignment in the class body, outside any method, is a **class attribute**:
one object shared by every instance, which is `static final` in Java and a
`const` in a `companion object` in Kotlin. Instance attributes, by contrast,
are the ones that appear when `__init__` assigns to `self`.

It is read back through the instance:

```python
if fired >= self.MAX_CATCH_UP_TICKS:
```

`self.X` looks on the instance first and falls back to the class, so this finds
the shared value — and it means a subclass can change the limit by declaring
its own, which a Java `static` field could not do through an instance
reference. The trap is the other direction: `self.MAX_CATCH_UP_TICKS = 10`
would not update the shared value, it would quietly create an *instance*
attribute of the same name shadowing it, leaving every other clock on 3.

That is the whole of the new syntax. Everything else — the `@property`, the
`Callable[[], None]`, the `float` annotations — has already appeared in
`flow.py`.

## The import that makes the clock swappable

```python
import time
...
while time.monotonic() >= self._next_deadline:
```

Calling the real clock directly, in the middle of the logic, looks
untestable. In Java it is: you would inject a `Clock` and pass a fake one in
tests, because `System.nanoTime()` is a static call you cannot intercept.
Python does not need the injection, and the reason is worth understanding
because it is the same rule behind a lot of Python testing.

`import time` binds the name `time` **in this module's namespace**. It is an
ordinary variable holding a module object, sitting alongside `GameClock` and
`MAX_CATCH_UP_TICKS`. And `time.monotonic()` is not resolved when the function
is defined — it is resolved **every time the line runs**, by looking up `time`
in the module's globals and then `monotonic` on whatever it finds.

So a test can put something else there:

```python
class FakeTime:
    def __init__(self, now=0.0):
        self.now = now
    def monotonic(self):
        return self.now

patcher = mock.patch.object(clock_module, "time", self.time)
```

That replaces the module-level name, and from then on every `time.monotonic()`
inside `clock.py` reads the fake's field. The test winds the clock by hand —
`self.time.now = 3.4` — and a session's worth of ticks costs nothing and lands
on exactly the same numbers every run. There is no waiting anywhere in
[`tests/test_clock.py`](../../tests/test_clock.py), which is why the whole
suite finishes in a quarter of a second.

Two things follow from the same rule and are worth carrying elsewhere.

**The lookup is by name, at call time.** This is why `from time import
monotonic` would have made the file *harder* to test: that binds the function
itself into the namespace, so replacing the module afterwards would change
nothing. Import the module, call through it, and the seam is free.

**It works because nothing is compiled.** The same lookup that makes a typo in
an attribute name a runtime error rather than a compile error is what lets a
test reach in and change one. It is one property, seen from two sides.

## Monotonic, not the wall clock

`time.monotonic()` is `System.nanoTime()`: a counter that only ever goes
forwards, with no defined zero, useful only for measuring gaps.
`time.time()` is `System.currentTimeMillis()`: the wall clock, which a user or
an NTP daemon can move backwards while you are waiting on it.

Anything that measures a duration or waits for a deadline should use the first,
and this file, `launcher.py` and the tests all do. The unit is a **float of
seconds** — `0.15` is 150 milliseconds. Python's standard library has no
`Duration` type; `time.sleep`, `time.monotonic` and every timeout in the
standard library take seconds as a float, and the curses timeout in
`screen.py` takes milliseconds as an int because that is what the C API
underneath it wanted. The mismatch is real and neither side is wrong.

## Why the deadline is advanced and not reset

This is the heart of the file:

```python
while time.monotonic() >= self._next_deadline:
    self._next_deadline += self._interval
    fired += 1
    self._on_tick()
```

The obvious-looking alternative is `self._next_deadline = time.monotonic() +
self._interval` — schedule the next tick one interval from *now*. It is wrong,
and wrong in a way that does not show up in a short test.

Say the interval is 0.15 and the loop, busy drawing, does not poll until 0.16.

- **Advancing** sets the next deadline to 0.30. The tick was 10ms late but the
  *schedule* is untouched, and the following tick is still due at its original
  time. Lateness does not accumulate.
- **Resetting** sets it to 0.31. Those 10ms are now permanent, and the next
  tick inherits its own lateness on top. Every poll adds a little, the game
  runs slower and slower, and nothing ever gives it back.

At ten milliseconds a tick, an eight-minute session ends up half a minute
behind. That is the drift a fixed timestep exists to prevent, and the whole of
the fix is `+=` rather than `=`.

## The cap, and why it needs its own realignment

Advancing by whole intervals has a failure mode of its own. Suspend the process
— Ctrl-Z, or shut the laptop — and come back an hour later, and the deadline is
an hour in the past. A plain loop would then fire twenty-four thousand ticks as
fast as it could, each one moving the ghost and publishing a frame, with the
terminal locked solid until it caught up.

```python
if fired >= self.MAX_CATCH_UP_TICKS:
    if time.monotonic() >= self._next_deadline:
        self._next_deadline = time.monotonic() + self._interval
    break
```

Three ticks, then out. The inner test is the part that is easy to miss: after
breaking out we may still be behind, and simply leaving the deadline where it
is would mean the next `poll` fires three more, and the one after that three
more, working through the backlog a spoonful at a time and never catching up.
So when the clock is still behind after its allowance, the backlog is thrown
away and the deadline is measured afresh from the present. A game that missed
an hour resumes; it does not replay.

The inner `if` is not decoration — the case where three ticks *were* enough to
catch up has to leave the schedule alone, or it would introduce the very drift
the `+=` was written to avoid.

## What a JVM reader would have reached for

Every instinct a Java or Kotlin programmer has for "call this every 150ms" is
wrong here, and for one reason: `curses` is not thread-safe. A tick that
arrives on another thread while the main one is halfway through a refresh does
not corrupt the game's state — it corrupts the terminal.

| The instinct | Why not here |
|---|---|
| `ScheduledExecutorService.scheduleAtFixedRate` | Fires on a pool thread, so the ghost would move while the screen was being drawn |
| `Handler.postDelayed`, `javax.swing.Timer` | The right shape, but they need a framework event loop to post onto. This program's event loop is a `while True` in `main.py` |
| `delay(150)` in a coroutine | A dispatcher, and a second scheduling mechanism, for a program that has one loop and one thread |
| `Thread.sleep(0.15)` in the loop | Single-threaded, and much worse to play: sleeping is not reading the keyboard, so input would only be noticed seven times a second |

That last row is why the clock is polled rather than slept on. `main.py` blocks
for at most 33 milliseconds waiting for a key, then polls the clock and goes
round again, so a key press is acted on the moment it arrives while ticks stay
on their own schedule. The comment in that file puts it in one line: the
timeout is the input latency, not the frame rate.

## The method the game does not call

```python
def _seconds_until_next_tick(self) -> float:
    if not self._running:
        return self._interval
    return max(0.0, self._next_deadline - time.monotonic())
```

This is for a caller that wants to block exactly until the next tick is due,
and it is written so that caller never has to ask whether the clock is running:
a stopped clock hands back a whole interval, which is a sensible timeout rather
than a special value, and the `max` means a deadline already gone by gives 0.0
rather than something negative that a timeout would misread.

Nothing in the game calls it. `main.py` waits a fixed 33 milliseconds instead,
because it is waiting for a key rather than for a tick, and it wants the key
sooner than the tick. The method is exercised by
[the tests](../../tests/test_clock.py) and is the obvious thing to reach for if
the loop ever stops having something else to wait on.

## Traps

| Habit | What Python does |
|---|---|
| `static` cannot be shadowed | `self.X = 1` creates an instance attribute hiding the class one, for that object only |
| A direct call to the clock is untestable | Import the *module* and call through it, and a test can replace the name |
| `from x import y` and `import x` are the same | They are not, for testing: the first copies the function in, and puts it beyond reach |
| Wall clock for timing | Use `time.monotonic()`; the wall clock can move backwards |
| Timeouts are integers of milliseconds | Python's standard library takes floats of seconds. Curses is the exception, and only because C is underneath |
| Fixed-rate means reschedule from now | That accumulates lateness. Advance by whole intervals instead |

## Where to go next

That is the whole of `util`. The layer above it is
[`view_model.py`](../../terminalgame/presentation/view_model.py), whose `tick`
is the callback this clock holds, and which
[its own lesson](view_model_py.md) covers.
[The lifecycle document](../LIFECYCLE.md) says what a tick does once it
arrives, and what stops it arriving when the game is over.
