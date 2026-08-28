# Enough Python to read `view_model.py`

For somebody fluent in Kotlin or Java who has not written Python. It covers the
subset the game's [view model](../../terminalgame/presentation/view_model.py)
actually uses, and nothing else. Every snippet below is from that file.

## Five differences to absorb before any syntax

**Indentation is the block.** No braces, no semicolons. A colon opens a block
and indentation closes it. Mis-indent and you get a different program, not a
syntax error.

**Type hints are decoration.** `def _odd(size: int) -> int` looks like Kotlin,
but nothing checks it at runtime and nothing optimises on it. `Optional[int]` is
`Int?` in intent only — pass a string and Python happily runs until something
breaks. That is why this repository runs `mypy` separately.

**No `new`, and no field declarations.** `GameViewModel(seed=7)` calls the
class. Attributes spring into existence when first assigned in `__init__`; there
is no list of fields anywhere. What a Kotlin class declares in its header,
Python discovers as it runs.

**`self` is an explicit first parameter.** `def tick(self)` is called as
`vm.tick()`. Kotlin's implicit `this` is spelled out, every method, every
attribute: `self._score`, never bare `_score`.

**A file is a module, and top-level code runs on import.** No
one-public-class-per-file rule. The validation loop near the top of this file
executes the moment anything imports it — closer to a Kotlin `object`'s `init`
block than to anything static.

## The constructs, in the order they appear

### Imports

```python
from ..util.flow import StateFlow
```

The dots are package-relative, `..` meaning "up one package". This is why the
game must be started with `python3 -m terminalgame.app.main`: run the file by
path and the relative imports have no package to resolve against.

### Constants

```python
_PILL = "▪"
```

No `val`; capitals are convention. The leading underscore means "private to this
module", enforced by **nothing**. It is a note to the reader, not the compiler.

### One line, two traps

```python
_PILL_CELL = (_PILL + " " * (CELL_COLS - 1),) * CELL_ROWS
```

`" " * 1` repeats a *string*; `(...) * CELL_ROWS` repeats a *tuple*. And the
trailing comma before the `)` is what makes it a one-element tuple: `("a")` is
just a string in brackets, `("a",)` is a tuple. Kotlin: `listOf("▪ ")`.

### Dicts as switch

Python has no `switch`. `_WALL_GLYPH` is a `mapOf` from a bitmask to a glyph,
and `_WALL_GLYPH[sides]` is the lookup that replaces sixteen `when` branches.

### Comprehensions

The one construct with no Kotlin keyword, though the idea is familiar:

```python
turns = [
    step
    for step in ((-1, 0), (1, 0), (0, -1), (0, 1))
    if step != back
    and self._maze.is_open(self._ghost_row + step[0], self._ghost_col + step[1])
]
```

Read it as `sequence.filter { ... }.map { ... }` written back to front: *what to
keep* first, then *where from*, then *the condition*. `{len(_line) for _line in
_art}` is the same thing producing a `Set`.

### Tuple unpacking

| Python | Kotlin |
|---|---|
| `d_row, d_col = self._ghost_step` | `val (dRow, dCol) = ghostStep` |
| `walls, pills = [], []` | two declarations at once |
| `self._maze.is_open(*ahead)` | spread a pair into two arguments |

### Lists versus tuples

`MutableList` versus an immutable one, and the distinction drives real code
here: `list(self._pills)` to get something editable, `tuple(self._pill_rows)` to
publish something that cannot be edited.

### Class, initialiser, property

```python
class GameViewModel:
    def __init__(self, seed: Optional[int] = None) -> None:
        self._score = 0

    @property
    def state(self) -> StateFlow[ViewState]:
        return self._state
```

`__init__` is the constructor body. `@property` is Kotlin's
`val state get() = ...`, called as `vm.state` with no parentheses. Names with
double underscores either side — `__init__`, `__repr__` — are Python's operator
conventions, the equivalent of Kotlin's `operator fun`.

### None

`None` is `null`, and the idiom is `is not None` rather than `!= None`. `is`
compares identity, and `None` is a singleton, so identity is the honest test.

## Two methods, annotated

Taking a pill:

```python
char_row, char_col = row * CELL_ROWS, col * CELL_COLS   # unpack a 2-tuple
line = self._pill_rows[char_row]                        # a str
if line[char_col] != _PILL:                             # index a string -> 1-char string
    return False                                        # no Boolean box, just False
self._pill_rows[char_row] = (
    line[:char_col] + " " + line[char_col + 1:]         # slices: [start:end), end omitted = to the end
)
self._pills = tuple(self._pill_rows)                    # freeze a copy
self._pills_left -= 1                                   # no ++
return True
```

Strings are immutable, as in Java — hence rebuilding the row rather than
assigning into it. `line[:n]` and `line[n+1:]` are `substring(0, n)` and
`substring(n+1)`; negative indices count from the end, so `line[-1]` is the last
character.

Moving the ghost:

```python
if not turns:            # an empty list is falsey -- Kotlin: if (turns.isEmpty())
    turns = [back]
self._ghost_step = self._rng.choice(turns)
self._ghost_row += self._ghost_step[0]
```

`if not turns` is the idiom you would write as `isEmpty()`. Empty list, empty
string, `0` and `None` are all falsey — convenient, and the source of bugs when
`0` is a legitimate value.

## Traps your Kotlin instincts will set

| Habit | What Python does |
|---|---|
| `("x")` is a 1-tuple | It is a string. You need `("x",)` |
| `_private` is enforced | It is not. Nothing stops `vm._score = 999` |
| Type hints are checked | They are not. Run `mypy` or do not rely on them |
| Overload by signature | No overloading. Default and keyword arguments instead |
| `/` on ints gives an int | `/` gives a float; `//` floors. Hence `GRID_ROWS // 2` |
| `==` for identity | `==` is `equals`; `is` is reference identity |
| Declare fields | Fields exist only once assigned — typo a name in `__init__` and you have silently created a second attribute |

One more worth knowing, though it is not in this file: a default argument like
`def f(items=[])` is evaluated **once**, at definition, and shared across every
call. It is the classic Python bug.

## What you can skip

`Tuple[str, ...]` just means "a tuple of any number of strings". The `-> None`
return hints are noise you can read past. The `Args:` and `Returns:` blocks in
the docstrings are conventional formatting, not syntax.

Genuinely absent from Python, and worth not looking for: interfaces, `final`,
checked exceptions, and any compile step at all. `_to_layers(maze)` takes an
untyped `maze` and works because it only ever calls `.rows` and `.is_open` —
duck typing, where the contract is what the code touches rather than what a type
declares.

## Where to go next in this codebase

[`flow.py`](../../terminalgame/util/flow.py) is ninety lines and covers the
other quarter of the language this code uses: generics via `Generic[T]`,
closures, and callables passed as values.
