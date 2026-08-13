"""Progress reporting.

Long operations narrate what they are doing. The CLI prints those lines, the web
UI appends them to a job log, and tests collect them in a list — so the services
depend on this interface rather than on `print`.
"""
from typing import Callable, Iterable, Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    def emit(self, message: str) -> None:
        ...


class NullReporter:
    """Discards everything. The default, so no service has to check for None."""

    def emit(self, message: str) -> None:
        return None


class PrintReporter:
    def emit(self, message: str) -> None:
        print(message)


class CallbackReporter:
    """Adapts the `on_event=lambda m: ...` callbacks the old API used."""

    def __init__(self, callback: Callable[[str], None]):
        self._callback = callback

    def emit(self, message: str) -> None:
        self._callback(message)


class ListReporter:
    """Collects messages — used by tests and by the job log."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        self.messages.append(message)


class CompositeReporter:
    """Fans one message out to several reporters (log it and print it)."""

    def __init__(self, reporters: Iterable[ProgressReporter]):
        self._reporters = list(reporters)

    def emit(self, message: str) -> None:
        for reporter in self._reporters:
            reporter.emit(message)


def resolve(reporter: ProgressReporter | Callable[[str], None] | None) -> ProgressReporter:
    """Accept a reporter, a plain callable, or nothing."""
    if reporter is None:
        return NullReporter()
    if callable(reporter) and not isinstance(reporter, ProgressReporter):
        return CallbackReporter(reporter)
    return reporter
