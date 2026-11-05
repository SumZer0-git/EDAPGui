"""Shared exceptions and enums."""

from enum import Enum


class EdapInterruptError(Exception):
    """Exception used to unroll the call tree to stop execution."""

    pass


class ScTargetAlignReturn(Enum):
    Lost = 1
    Found = 2
    Disengage = 3


class FsdAssistResult(Enum):
    RouteComplete = 1
    InSystemTarget = 2
    Failed = 3
