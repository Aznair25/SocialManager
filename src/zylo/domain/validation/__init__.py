"""Deck validation: rules, per-field constraints, and the validator that runs them."""
from .constraints import (
    BalancedHighlights,
    FieldConstraint,
    FieldContext,
    MaxLength,
    NoEmoji,
    NoExclamation,
    default_field_constraints,
)
from .report import Issue, Severity, ValidationReport, error, warning
from .rules import ValidationRule, default_rules
from .specs import MIDDLE_ROLES, SLIDE_SPECS, SlideSpec, limits_as_prompt_data, spec_for
from .validator import DeckValidator

__all__ = [
    "BalancedHighlights",
    "DeckValidator",
    "FieldConstraint",
    "FieldContext",
    "Issue",
    "MIDDLE_ROLES",
    "MaxLength",
    "NoEmoji",
    "NoExclamation",
    "SLIDE_SPECS",
    "Severity",
    "SlideSpec",
    "ValidationReport",
    "ValidationRule",
    "default_field_constraints",
    "default_rules",
    "error",
    "limits_as_prompt_data",
    "spec_for",
    "warning",
]
