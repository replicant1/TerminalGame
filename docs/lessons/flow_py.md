# Enough Python to read `flow.py`

For somebody fluent in Kotlin or Java. The file is
[`terminalgame/util/flow.py`](../../terminalgame/util/flow.py), it is
eighty-five lines, and it is a deliberate imitation of
`kotlinx.coroutines.StateFlow` — so most of it can be learned by asking how the
Python differs from the Kotlin you already know.

It is the companion to [the `view_model.py` lesson](view_model_py.md), which
covers the everyday syntax. This one covers generics, functions as values, and
closures.

## What it is, in one paragraph

A value that can be watched. It always holds something, a new subscriber is
handed the current value the moment it subscribes, and emitting a value equal to
the one already held does nothing at all. Those are `StateFlow`'s three
promises, and this file keeps them in eighty-five synchronous lines with no
coroutines, no locks and no threads.

## Generics: two lines where Kotlin has two characters

```python
T = TypeVar("T")

class StateFlow(Generic[T]):
```

Kotlin writes `class StateFlow<T>`. Python has no syntax for declaring a type
parameter, so you make one as a **value** — `TypeVar("T")` — and then inherit
from `Generic[T]` to say the class is parameterised by it. The name is repeated
because the string is what appears in error messages; nothing connects it to the
variable except convention.

**Where Kotlin writes angle brackets, Python writes square ones.** Kotlin's
`StateFlow<ViewState>` is Python's `StateFlow[ViewState]`, and it means the same
thing: a `StateFlow` whose `T` is `ViewState`. The brackets are square because
`<` and `>` are already comparison operators, so angle brackets could not be
parsed unambiguously; Python reused the subscript operator instead — the same
`[]` as in `line[3]`.

One thing has no Kotlin equivalent: that is an **expression**, not syntax. It
runs, and it produces an object:

```python
>>> StateFlow[ViewState]
terminalgame.util.flow.StateFlow[terminalgame.presentation.state.ViewState]
>>> type(StateFlow[ViewState]).__name__
'_GenericAlias'
```

Kotlin's `<ViewState>` is erased by the compiler and does not exist at runtime.
Python's is a small object that remembers "StateFlow, parameterised by
ViewState", and you could assign it to a variable if you wanted to.

In this codebase it appears as an annotation only:

```python
self._state: StateFlow[ViewState] = StateFlow(self._build_state())
#            |___ annotation: T is ViewState ___|  |___ construction, no brackets ___|
```

The brackets describe the variable, on the left. The construction on the right
does not need them, because the value passed in decides what is in there. The
same nesting works inside other types: `List[Callable[[T], None]]` is
`List<(T) -> Unit>`.

Neither language checks any of this at runtime, but Python does not check it
even a little: a `StateFlow[ViewState]` will hold a string without complaint.
`mypy` is the only thing that would object.

## Functions are values, and `Callable` is their type

```python
def subscribe(self, on_each: Callable[[T], None]) -> Callable[[], None]:
```

| Python | Kotlin |
|---|---|
| `Callable[[T], None]` | `(T) -> Unit` |
| `Callable[[], None]` | `() -> Unit` |
| `None` as a return type | `Unit` |

The parameter list is a *list* in the brackets, which is why the empty case is
`Callable[[], None]` with two pairs of brackets — one for the type, one for the
empty parameter list.

A function passed in is called exactly like any other function:

```python
self._subscribers.append(on_each)   # store it
on_each(self._value)                # call it
```

There is no `invoke`, no functional interface, and no distinction between a
function and a lambda. This is why the screen can subscribe with

```python
self._unsubscribe = view_model.state.subscribe(self.render)
```

`self.render` is a **bound method** — Kotlin's `::render`, except you do not
need the `::`. Referring to a method without calling it hands over the method
with its receiver attached.

## Closures, and returning one

```python
def subscribe(self, on_each):
    self._subscribers.append(on_each)
    on_each(self._value)

    def unsubscribe() -> None:
        if on_each in self._subscribers:
            self._subscribers.remove(on_each)

    return unsubscribe
```

A `def` inside a `def` is just a local binding, and it closes over the enclosing
variables — `on_each` and `self` here. Returning it gives the caller something
to hold, the way a Kotlin `Job` is held: call it and the subscription ends.

Two things to know that Kotlin does not make you think about.

**A closure captures the variable, not the value.** In Kotlin a captured `val`
is fixed. In Python the closure sees whatever the variable holds *when the
closure runs*. The classic bite:

```python
fs = []
for i in range(3):
    fs.append(lambda: i)      # all three read the same i
[f() for f in fs]             # [2, 2, 2], not [0, 1, 2]
```

`unsubscribe` is safe from this because `on_each` is a parameter, rebound on
every call to `subscribe`, so each closure gets its own.

**Assigning to an outer variable needs a keyword.** Reading an enclosing
variable works; assigning to it makes it local unless declared `nonlocal` (or
`global` at module level). No such assignment happens here, which is why the
file never mentions either keyword.

## `in`, `remove`, and what equality means

```python
if on_each in self._subscribers:
    self._subscribers.remove(on_each)
```

`in` is a linear search using `==`, and `remove` deletes the **first** element
that compares equal. For functions, `==` is identity, so this removes exactly
the subscription that was made.

For the values flowing through, `==` means something richer:

```python
if new_value == self._value:
    return False
```

`==` calls `__eq__`. A plain Python class does not define one, so it falls back
to identity — two separately built objects would never be equal, and this
comparison would never fire. It works because `ViewState` is a **frozen
dataclass**, which generates `__eq__` from the fields, exactly as Kotlin's
`data class` generates `equals`. That one decision in `state.py` is what makes
this line worth writing.

`is` is the identity test, and it is not interchangeable: `==` asks whether two
frames say the same thing, `is` asks whether they are the same object.

## Copying a list to iterate it

```python
# Copy the list so a subscriber may unsubscribe during delivery.
for subscriber in list(self._subscribers):
    subscriber(new_value)
```

`list(x)` is a shallow copy — Kotlin's `toList()`. Without it, a subscriber that
unsubscribes while being called would mutate the list being iterated. Java
raises `ConcurrentModificationException` for this. Python does something worse:
it quietly skips the next element and carries on, which is a bug you find weeks
later.

## The property

```python
@property
def value(self) -> T:
    return self._value
```

Kotlin's `val value get() = _value`. Called as `flow.value`, with no
parentheses. There is no setter, so `flow.value = x` raises `AttributeError` —
read-only by omission rather than by keyword.

## How it differs from the Kotlin it imitates

| kotlinx `StateFlow` | This file |
|---|---|
| `collect` is a `suspend` function | `subscribe` is an ordinary call |
| Subscribers resume on a dispatcher | Subscribers run **inline**, on the thread that emitted |
| Cancellation via a `Job` or scope | `subscribe` returns a function that unsubscribes |
| Thread-safe, with locks | Single-threaded by design, so no locks exist |
| Operators: `map`, `filter`, `combine` | None. `_update` is the only extra |

The single-threadedness is not laziness. `curses` is not thread safe, so every
emission happening on the main loop's thread is what keeps a frame from being
half-drawn — the reasoning is in
[the clock tick scenario](../scenarios/a-clock-tick-moves-the-ghost-and-repaints-the-screen.md).

## Traps

| Habit | What Python does |
|---|---|
| Generics constrain at runtime | Nothing is checked. `StateFlow[ViewState]` will hold anything |
| A captured variable is frozen | The closure sees its later value; watch loops |
| Assigning to an outer variable works | It creates a local instead, unless you write `nonlocal` |
| Value equality comes for free | Only from `dataclass`, `NamedTuple` or a hand-written `__eq__`; otherwise `==` is identity |
| Mutating a collection while iterating throws | It silently skips elements |
| A read-only property needs a keyword | It is read-only because no setter was written |

## Where to go next

[`clock.py`](../../terminalgame/util/clock.py) is the other half of `util`, at
about the same length, and introduces almost no new *syntax* — which is the
point: after these two lessons the utility layer should read as ordinary code.
What it does introduce is worth having, and [its lesson](clock_py.md) spends
its length on two things rather than on grammar: how `import time` leaves a
seam a test can reach through to wind the clock by hand, and why a tick
deadline has to be advanced rather than reset.
