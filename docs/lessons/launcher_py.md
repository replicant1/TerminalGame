# Enough Python to read `launcher.py`

For somebody fluent in Kotlin or Java. The file is
[`terminalgame/app/launcher.py`](../../terminalgame/app/launcher.py), it is
four hundred and sixty lines, and it is the least game-like code in the
program: it opens a window, waits for a file to change, and forwards an exit
code.

It is also the file where Python's standard library does most of the work, so
this lesson is largely about that library — processes, files written safely,
signals used as questions — rather than about syntax. The syntax it does
introduce is small: keyword arguments, multiple return values, and one
formatting rule that bites everybody once.

[The `view_model.py` lesson](view_model_py.md) covers the everyday syntax, and
[the `screen.py` lesson](screen_py.md) covers the `with` statement this file
uses to write a file.

## What it is, in one paragraph

`python3 -m terminalgame.app.main` should behave like an ordinary command:
block while the game runs, then exit with the game's exit code. But the game
runs in a *different* window, in a different process, which this file asks
macOS to create. So the launcher stays behind in the original terminal watching
a small file — the sentinel — that the game writes twice: once to say it
started, once to say how it ended.

## A module of functions, and no class

There is no `Launcher` class. The file is a module holding functions and
constants, and other modules call them as `launcher.launch(...)`.

This is not an omission. In Python a module *is* the namespace, so a class
holding nothing but static methods would be a container inside a container.
Kotlin's top-level functions in a file are exactly the same idea; Java's
`static` on a `final class` is the workaround for not having them.

The underscore convention does the rest of the work: `launch`,
`announce_started`, `announce_finished` and `_is_supported` are the entry
points, and everything named `_like_this` is internal. Nothing enforces it.

## Running another program

```python
result = subprocess.run(
    ["/usr/bin/osascript", "-e", script],
    capture_output=True,
    text=True,
    check=True,
)
```

`ProcessBuilder`, with better defaults. Four things to know:

**The argument is a list, not a string.** Each element is one argv entry,
handed to the operating system as-is. There is no shell involved, so spaces,
quotes and semicolons inside an element are data rather than syntax — the
injection class of bug simply does not arise. Passing a single string instead
would need `shell=True`, which this file never does.

**`capture_output=True`** collects stdout and stderr onto the result rather
than letting them land on the terminal.

**`text=True`** decodes them to `str`. Without it you get `bytes`, and every
comparison against a string literal silently fails. This is the flag people
forget.

**`check=True`** raises `CalledProcessError` on a non-zero exit code, instead
of returning quietly. That is what turns a refusal by Terminal.app into an
exception this file can translate:

```python
except subprocess.CalledProcessError as error:
    raise LaunchError("Terminal.app refused to open the window: {}".format(
        (error.stderr or "").strip()
    ))
```

`as error` binds the exception, like Java's `catch (E error)`. The `or` inside
is Kotlin's elvis in disguise: `a or b` evaluates to `a` when `a` is truthy and
`b` otherwise, so `error.stderr or ""` is `error.stderr ?: ""` — and also
covers an empty string, since that is falsey too.

## The formatting rule that bites everybody

The AppleScript is a triple-quoted string — `'''...'''` spans lines, Kotlin's
`"""..."""` — filled in with `.format()`:

```python
script = _SPAWN_SCRIPT.format(
    command=escaped, rows=rows, cols=cols, title=WINDOW_TITLE, ...
)
```

The names are keyword arguments matching `{command}`, `{rows}` and so on in the
template. Kotlin's `"$command"` interpolation happens at compile time and can
only read variables in scope; `.format()` happens at run time on any string,
which is why a template can live in a constant at the top of the file.

Now the trap. AppleScript uses braces for its own list literals, and this line
is in the template:

```applescript
set bounds to {{nx, ny, nx + wd, ny + ht}}
```

`{{` and `}}` are how you write a **literal brace** in a format string, the way
`\\` writes a literal backslash. After `.format()` runs, the AppleScript
receives `{nx, ny, nx + wd, ny + ht}`. Single braces there would have been read
as a field name and raised `KeyError: 'nx'`.

Two levels of quoting are in play here, and it is worth seeing them separately.
The command is quoted for the **shell** with `shlex.quote` — the standard
library's version of "wrap this so a shell treats it as one word" — and then
escaped again for the **AppleScript string literal** it is embedded in:

```python
escaped = command.replace("\\", "\\\\").replace('"', '\\"')
```

In a normal Python string `\\` is one backslash, so that reads: double every
backslash, then put a backslash in front of every double quote.

## Talking to the child process without argv

```python
if os.environ.get(ENV_CHILD) == "1":
```

`os.environ` is a dictionary of the environment, and `.get` returns `None` for
a name that is not set rather than raising. Every value is a **string** —
hence comparing against `"1"` and not `1`.

The environment is used here instead of command-line arguments for a reason
worth knowing, because it explains an otherwise odd design: Terminal.app puts
the running process's arguments in the window's title bar, and that part is not
scriptable, so a `--sentinel /var/folders/...` argument would be on display for
the whole game. The environment is invisible.

## Writing a file that a reader cannot catch half-written

```python
temporary = sentinel_path + ".tmp"
with open(temporary, "w") as handle:
    handle.write(text)
    handle.flush()
    os.fsync(handle.fileno())
os.replace(temporary, sentinel_path)
```

`with open(...) as handle:` is the context manager from
[the `screen.py` lesson](screen_py.md): the file closes at the end of the
block, exception or not — Kotlin's `File.writer().use { }`.

The rest is the write-and-rename idiom, and each step earns its place.
`flush()` pushes Python's buffer into the operating system; `os.fsync` pushes
the operating system's buffer onto the disk; `os.replace` renames one file over
another **atomically**, so a reader either sees the old file or the new one and
never a partial line. It is `Files.move(..., ATOMIC_MOVE)`, and it differs from
`os.rename` in overwriting an existing destination on every platform.

The launcher is polling this file every hundred milliseconds, which is exactly
the reader this protects.

## Exceptions as flow control, narrowly

```python
try:
    with open(sentinel) as handle:
        state, _, raw = handle.read().strip().partition(" ")
    return state, int(raw)
except (OSError, ValueError):
    return None, 0
```

Three things at once.

**A tuple catches several types** — Java's `catch (OSError | ValueError e)`.
Here it covers both *the file is not there yet* (`OSError`) and *the file is
there but holds half a line* (`ValueError`, from `int`).

**`partition` returns three values**: the part before the separator, the
separator itself, and the part after. `"pid 1234".partition(" ")` is `("pid",
" ", "1234")`. The middle one is bound to `_`, which is the convention for a
value you are deliberately ignoring — it is an ordinary variable name, not
syntax.

**Returning two values** is returning one tuple: `return state, int(raw)` and
`return None, 0` both build a pair, and the caller unpacks it —
`exit_code, child_pid = _wait_for_child(sentinel)`. The annotation spells it
out as `Tuple[Optional[str], int]`. Kotlin would need a `Pair` or a data class.

## Asking whether a process is alive

```python
try:
    os.kill(pid, 0)
except ProcessLookupError:
    return False
except PermissionError:
    return True
return True
```

`os.kill` is misnamed: it sends a signal, and signal **0** is the one that
sends nothing. The call exists entirely for its error behaviour — no such
process raises `ProcessLookupError`, and a process owned by somebody else
raises `PermissionError`, which *proves it exists*. That second branch reads
like a mistake and is the correct answer.

Both are subclasses of `OSError`, which is why the broader `except OSError`
elsewhere in the file would have caught them too. Python's exception hierarchy
does this a lot: catching a parent quietly catches the children.

## Deadlines, not durations

```python
deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
while True:
    ...
    if child_pid is not None and not _process_alive(child_pid):
        return 0, None
    time.sleep(POLL_INTERVAL_SECONDS)
```

`time.monotonic()` is `System.nanoTime()` — a clock that only goes forwards and
is unaffected by the system clock being set. `time.time()` is the wall clock,
and using it for a timeout means a machine syncing its clock can expire your
deadline. Seconds are floats, so `time.sleep(0.1)` is a tenth of a second.

The loop is `while True` with returns inside rather than a condition at the
top, because it has three ways out — an exit code arrived, the process
vanished, or it never started at all — and none of them is the loop's
condition.

## Cleaning up

```python
try:
    ...
finally:
    _cleanup(directory, sentinel)
```

`try`/`finally` with no `except`: run this whatever happens, but do not handle
anything. Identical to Java. It is used rather than a `with` because what needs
removing is a temporary directory made by `tempfile.mkdtemp`, which hands back
a path rather than a managed object.

Inside `_cleanup`, each removal is wrapped in its own `try`/`except OSError:
pass`, because tidying up is best-effort: a file that is already gone is not a
problem worth propagating.

## Traps

| Habit | What Python does |
|---|---|
| A command is a string | It is a list of argv entries. No shell, so no quoting rules |
| Subprocess output is text | It is `bytes` unless you pass `text=True` |
| A non-zero exit code raises | Only with `check=True`; otherwise it is just a field on the result |
| `{` in a format string | Write `{{` for a literal brace, or get `KeyError` |
| Environment values have types | They are always strings. Compare against `"1"` |
| `os.kill` kills | Signal 0 sends nothing and is used to ask whether a pid exists |
| `PermissionError` means failure | Here it means the process is alive and owned by somebody else |
| Catch the exact type | Catching `OSError` also catches `ProcessLookupError` and `PermissionError` |
| `rename` is `rename` | `os.replace` is the one that overwrites atomically everywhere |
| Timeouts off the wall clock | Use `time.monotonic()`; the wall clock can move under you |

## What you can skip

The AppleScript itself is a language you do not need to learn to follow the
Python. It creates a tab, sets its size and font, finds the window that
contains it by matching the tab's `tty`, and moves it next to whatever window
was in front. The comments in `_SPAWN_SCRIPT` say why each step is in the order
it is.

`_project_root()` is three nested `os.path.dirname` calls with the answer
written beside each one in a comment — read the comments, not the nesting.

## Where to go next

[The launcher scenario](../scenarios/the-launcher-opens-the-game-in-its-own-terminal-window.md)
walks the same code as a sequence of messages between the launcher, osascript,
Terminal.app and the child, which is the view this lesson leaves out.
[The glossary](../GLOSSARY.md) defines sentinel, child and the rest of the
vocabulary the file assumes.
