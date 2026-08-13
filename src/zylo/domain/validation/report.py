"""Validation results.

Errors block a render; warnings are printed and moved past. Issues keep the
order the rules produced them in, because the generator feeds the error list
straight back to the model as a correction list and stable ordering makes those
retries reproducible.
"""
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    severity: Severity
    message: str

    def __str__(self) -> str:
        return self.message


def error(message: str) -> Issue:
    return Issue(Severity.ERROR, message)


def warning(message: str) -> Issue:
    return Issue(Severity.WARNING, message)


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[Issue, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, issues) -> "ValidationReport":
        return cls(tuple(issues))

    def _messages(self, severity: Severity) -> list[str]:
        return [i.message for i in self.issues if i.severity is severity]

    @property
    def errors(self) -> list[str]:
        return self._messages(Severity.ERROR)

    @property
    def warnings(self) -> list[str]:
        return self._messages(Severity.WARNING)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:
        return self.ok

    def summary(self) -> str:
        return f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"

    def joined_errors(self) -> str:
        return "; ".join(self.errors)
