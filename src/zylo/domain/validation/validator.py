"""The validator: a composition of rules, nothing more.

It knows how to run rules and collect issues. It knows nothing about what makes
a deck valid — that lives in the rules, which is what makes the rule set
extensible without touching this class.
"""
from typing import Iterable

from ..deck import Deck
from .report import ValidationReport
from .rules import ValidationRule, default_rules


class DeckValidator:
    def __init__(self, rules: Iterable[ValidationRule]):
        self._rules = list(rules)

    @classmethod
    def with_default_rules(cls) -> "DeckValidator":
        return cls(default_rules())

    def validate(self, deck: Deck) -> ValidationReport:
        issues = []
        for rule in self._rules:
            issues.extend(rule.check(deck))
        return ValidationReport.of(issues)

    def with_rule(self, rule: ValidationRule) -> "DeckValidator":
        """A new validator with one more rule — the original is left alone."""
        return DeckValidator([*self._rules, rule])

    @property
    def rules(self) -> tuple[ValidationRule, ...]:
        return tuple(self._rules)
