"""Shared types used by questionnaire colors and triage."""

from enum import IntEnum


class Severity(IntEnum):
    GREEN = 1
    YELLOW = 2
    ORANGE = 3
    RED = 4
