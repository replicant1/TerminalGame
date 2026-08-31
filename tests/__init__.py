"""The test suite.

Plain unittest, run from the project root:

    python3 -m unittest discover -s tests -t .

Nothing here imports anything the game does not, so the suite runs on a bare
interpreter with no terminal attached: curses is only ever driven through a
fake window, and the one clock is fed a fake `time`.
"""
