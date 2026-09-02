# Enough Python to read `screen.py`

For somebody fluent in Kotlin or Java. The file is
[`terminalgame/ui/screen.py`](../../terminalgame/ui/screen.py), it is three
hundred and thirty-six lines, and it is where every curses call in the program
lives. One other file imports the module — `app/main.py`, for the `KEY_UP` and
`KEY_RESIZE` constants it compares key codes against — and it calls nothing.

Two things stand between you and reading it, and only one of them is Python.
The language part is the context manager protocol and a handful of loop and
indexing idioms; the rest is the curses vocabulary, which is a 1980s C API with
its own opinions and its own argument order. Both are covered here.

It assumes [the `view_model.py` lesson](view_model_py.md) for everyday syntax
and [the `flow.py` lesson](flow_py.md) for callables, since `attach` hands a
bound method to a `StateFlow`.

## What it is, in one paragraph

An object that owns the terminal for as long as the game runs. It takes the
terminal over, subscribes to the ViewModel, paints every frame it is handed,
reads keys, and gives the terminal back — in one piece, whether the game ended
well or badly. It holds no game state of its own: everything it draws arrives
as an argument.

## The context manager: `with`, and the two methods behind it

This is the construct the file is built around, and `main.py` uses it like
this:

```python
with GameScreen() as screen:
    run(screen)
```

Java's try-with-resources and Kotlin's `use` are the same idea, and the two
methods that implement it are the counterparts of `AutoCloseable`:

```python
def __enter__(self) -> "GameScreen":
    self.open()
    return self

def __exit__(self, exc_type, exc, tb) -> bool:
    self.close()
    return False
```

Three things are worth pausing on.

**`__enter__` decides what `as` binds.** Whatever it returns is what lands in
`screen`. Returning `self` is the usual choice, but a context manager is free
to hand back something else entirely — which is why `open()` and `__enter__`
are separate methods here rather than one.

**`__exit__` is told how the block ended.** The three parameters are the
exception type, the exception, and the traceback, all `None` when the block
finished normally. `close()` is called either way, which is the whole point:
the terminal is handed back even when the game crashes, and a terminal left in
raw mode with no echo is a terminal you have to close the window on.

**The return value is a trap with no Java equivalent.** Returning a *truthy*
value from `__exit__` **swallows the exception** — the `with` block exits
quietly and the program carries on as though nothing had happened. Java cannot
do this; `close()` has no say in whether the exception propagates. That is why
the `return False` is written out and documented rather than left implicit. A
bare `return`, or falling off the end, gives `None`, which is falsey and
behaves the same way — but says it by accident.

The same protocol turns up in `launcher.py` as `with open(path, "w") as
handle:`, which is the everyday use: a file that closes itself.

**The name in quotes.** `-> "GameScreen"` is a forward reference. At the moment
the `def` line runs, the class is still being built and the name does not exist
yet, so the annotation is written as a string and resolved later if anything
asks. Kotlin never makes you think about this because annotations are not
executable there. Python's are.

## The idioms, in the order they appear

### Two values out of one call

```python
height, width = window.getmaxyx()
```

Tuple unpacking, as in the view model lesson — but note the order. Curses
counts **y before x**, rows before columns, everywhere: `getmaxyx`, `move(y,
x)`, `addnstr(y, x, ...)`. The whole file follows suit, and every helper takes
`row` before `col`. Getting this backwards produces a program that draws
nothing rather than one that fails to compile.

### `enumerate`

```python
for row_index, row_text in enumerate(rows):
```

Kotlin's `forEachIndexed`, or `withIndex()`. It yields `(index, item)` pairs,
which the `for` header unpacks in place. The index comes first.

### Unpacking in the loop header

```python
for rows, color in ((state.walls, COLOR_WALL), (state.pills, COLOR_PILL)):
```

A tuple of two pairs, unpacked one pair at a time — the loop body is written
once and runs for each layer. Kotlin would reach for `listOf(walls to WALL,
pills to PILL).forEach { (rows, colour) -> ... }`, which is the same shape with
more punctuation.

The dictionary version adds one level:

```python
for slot, (foreground, attribute) in palette.items():
```

`palette.items()` yields `(key, value)` pairs, and the value is itself a pair,
so the brackets on the right unpack it in place. `.items()` is Kotlin's
`entries`, except you get a real tuple rather than a `Map.Entry`.

### The conditional expression, written backwards

```python
return None if key == -1 else key
```

Kotlin writes `if (key == -1) null else key`. Python puts the **value first**
and the condition in the middle. It reads as an English sentence — *None, if
the key is -1, otherwise the key* — and it catches every Kotlin reader once.

### Chained comparison

```python
if not (0 <= row < height) or col >= width:
```

`0 <= row < height` is one expression meaning `0 <= row and row < height`, with
`row` evaluated once. Kotlin's nearest equivalent is `row in 0 until height`.
No other C-family language does this, and it is worth recognising rather than
misreading it as a comparison against a Boolean.

### `dict.get` with a default

```python
attribute = self._color_pairs.get(color_slot, curses.A_NORMAL)
```

`getOrDefault`. Plain `self._color_pairs[color_slot]` would raise `KeyError` on
a terminal with no colour, where the dictionary was never filled in.

### A `while` loop, on purpose

`_put_runs` walks a row of text looking for runs of non-space characters, and
it does it with an index and a `while` rather than a comprehension:

```python
col, end_of_text = 0, len(text)
while col < end_of_text:
    if text[col] == " ":
        col += 1
        continue
    run_end = col
    while run_end < end_of_text and text[run_end] != " ":
        run_end += 1
    self._put(window, row, col, text[col:run_end], color_slot, height, width)
    col = run_end
```

Comprehensions produce one output per input. This produces one output per
*run*, and the index has to jump — which is exactly the case they cannot
express. `text[col:run_end]` is `substring(col, runEnd)`, end-exclusive.

### `try` / `except` / `pass`

```python
try:
    window.move(height - 1, 0)
except curses.error:
    pass
```

`except` is `catch`, `pass` is an explicit empty block — Python has no `{}` to
leave empty, so it needs a word that does nothing. Nothing here is checked, in
the Java sense: no method declares what it throws, and catching narrowly is a
choice rather than an obligation.

Swallowing an exception is a decision the file makes twice, both times for the
same reason: curses raises when you write to the bottom-right cell of a window,
which is a boundary condition rather than a failure.

## Enough curses to read the file

The API is C, wrapped thinly. Names are abbreviated to the point of being
initials, and the two-letter suffixes are meaningful: `yx` means the call takes
or returns y then x, `n` means it takes a maximum length.

| Call | What it does |
|---|---|
| `initscr()` | Takes over the terminal and returns the top-level window |
| `endwin()` | Gives it back. Not calling this leaves the shell unusable |
| `noecho()` / `echo()` | Stop, and restore, keys being printed as they are typed |
| `cbreak()` / `nocbreak()` | Deliver each key immediately, rather than a line at a time on Enter |
| `curs_set(0)` | Hide the caret, so it cannot flash across the playfield |
| `keypad(True)` | Decode arrow-key escape sequences into single `KEY_*` codes |
| `getmaxyx()` | The window's size, rows first |
| `erase()` | Blank the back buffer. `clear()` also forces a full physical repaint, which is the flicker this file avoids |
| `addnstr(y, x, s, n, attr)` | Write at most `n` characters at a position, in an attribute |
| `noutrefresh()` | Stage this window's changes without writing to the terminal |
| `doupdate()` | Write every staged change, in one pass |
| `getch()` | Read a key code, or `-1` when the timeout elapsed |
| `timeout(ms)` | Bound how long `getch` blocks |
| `update_lines_cols()`, `clearok(True)` | Re-measure after a resize, and force the next draw to repaint everything |
| `curses.error` | The one exception type the module raises |

The pairing of `noutrefresh` with `doupdate` is the part worth understanding,
because it is why the game does not flicker. A plain `refresh()` writes to the
terminal immediately, once per window. Staging the changes and then calling
`doupdate` once produces a single write per frame, and ncurses diffs the back
buffer against what is physically on screen, so only the character positions
that actually changed cost anything. That is the mechanism the
whole-frame-every-tick design leans on, and it is described in
[the unchanged-frame scenario](../scenarios/an-unchanged-frame-is-dropped-before-it-reaches-the-terminal.md).

Colour arrives through an indirection: `init_pair(slot, foreground,
background)` defines numbered pair `slot`, and `color_pair(slot)` turns that
number into an attribute you can `|` together with `A_BOLD` or `A_NORMAL`. The
bitwise or is the same one you know from Java. `use_default_colors()` is
wrapped in a `try` because it is an ncurses extension and not every terminal
has it.

Two calls in `open()` are not curses at all. `locale.setlocale(locale.LC_ALL,
"")` adopts the environment's locale, which has to happen before anything wide
or non-ASCII is drawn, and the escape sequence written straight to
`sys.stdout` asks the terminal to resize itself — a request a terminal is free
to ignore, which is what `TerminalTooSmall` reports.

The standard library also offers `curses.wrapper(func)`, which does the setup
and teardown around a function you pass it. You will not find it here: the
context-manager protocol does the same job, and it lets the screen be opened,
handed around and closed by the code that owns it rather than by a callback.

## Traps

| Habit | What this file does |
|---|---|
| `close()` cannot affect the exception | `__exit__` returning truthy swallows it. Hence the explicit `return False` |
| x before y | Curses is y first, always. Rows, then columns |
| `if (cond) a else b` | Python puts the value first: `a if cond else b` |
| `a < b && b < c` | Python chains: `a < b < c`, with `b` evaluated once |
| `map[key]` returns null | It raises `KeyError`. Use `.get(key, default)` |
| Annotations are inert | They are expressions, evaluated at definition, so a self-reference has to be a string |
| A resource closes itself | Only inside `with`. Calling `open()` by hand means calling `close()` by hand |

## Where to go next

[`launcher.py`](../../terminalgame/app/launcher.py) is the other half of the
platform-facing code, and [its lesson](launcher_py.md) covers processes, files
and the standard library corners this one does not touch. The vocabulary these
two files draw on — layer, glyph, sprite, playfield — is collected in
[the glossary](../GLOSSARY.md).
