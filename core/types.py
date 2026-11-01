"""Shared exceptions and enums."""

from enum import Enum


class EDAP_Interrupt(Exception):
    """Exception used to unroll the call tree to stop execution."""
    pass


class ScTargetAlignReturn(Enum):
    Lost = 1
    Found = 2
    Disengage = 3
