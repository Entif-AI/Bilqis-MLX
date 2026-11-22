"""Shared BAMF operator candidate-horizon limits.

The default remains conservative for ordinary human training. The maximum is an
explicit operator-selectable ceiling; teacher-owned interference policy may
shorten any configured horizon before candidate execution.
"""

DEFAULT_CANDIDATE_HORIZON = 16
MAX_CANDIDATE_HORIZON = 24

__all__ = ("DEFAULT_CANDIDATE_HORIZON", "MAX_CANDIDATE_HORIZON")
