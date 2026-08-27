"""A minimal, synchronous StateFlow -- the Python analogue of kotlinx.coroutines.StateFlow.

Deliberately single-threaded: curses is not thread-safe, so every emission
happens on the main loop's thread and subscribers run inline. That makes the
whole pipeline (tick -> state -> render) deterministic and free of locks.
"""

from typing import Callable, Generic, List, TypeVar

T = TypeVar("T")


class StateFlow(Generic[T]):
    """Holds a current value and notifies subscribers when it changes.

    Mirrors StateFlow semantics:
      - always has a value (no "empty" state)
      - new subscribers immediately receive the current value
      - conflated / distinct-until-changed: emitting an equal value is a no-op
    """

    def __init__(self, initial: T) -> None:
        self._value = initial
        self._subscribers: List[Callable[[T], None]] = []

    @property
    def value(self) -> T:
        return self._value

    def subscribe(self, on_each: Callable[[T], None]) -> Callable[[], None]:
        """Register a collector. It is invoked at once with the current value.

        Returns a function that unsubscribes, so callers can use it like a Job.
        """
        self._subscribers.append(on_each)
        on_each(self._value)

        def unsubscribe() -> None:
            if on_each in self._subscribers:
                self._subscribers.remove(on_each)

        return unsubscribe

    def emit(self, new_value: T) -> bool:
        """Publish a new value. Returns True if it differed from the last one.

        Equality is what makes this cheap: ViewState is a frozen dataclass, so
        an unchanged frame costs one comparison and does not touch the screen.
        """
        if new_value == self._value:
            return False
        self._value = new_value
        # Copy the list so a subscriber may unsubscribe during delivery.
        for subscriber in list(self._subscribers):
            subscriber(new_value)
        return True

    def update(self, transform: Callable[[T], T]) -> bool:
        """Emit transform(current) -- the equivalent of MutableStateFlow.update."""
        return self.emit(transform(self._value))
