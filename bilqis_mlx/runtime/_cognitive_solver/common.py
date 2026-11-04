"""Shared cognitive-solver wire identities and validation helpers."""
from __future__ import annotations

import re

from ...errors import ErrorBus, SCHOOL

GENERATION_BINDING_SCHEMA = "bilqis.c04.generation-binding/v1"
QUALIFIED_COMPOSITION_SCHEMA = "bilqis.c04.qualified-composition/v1"
SOLVE_BUDGET_SCHEMA = "bilqis.c04.solve-budget/v2"
SOLVE_CONTEXT_SCHEMA = "bilqis.c04.solve-context/v2"
NEURAL_REQUEST_SCHEMA = "bilqis.c04.neural-request/v1"
NEURAL_PROPOSAL_SCHEMA = "bilqis.c04.neural-proposal/v1"
CAPABILITY_RESULT_SCHEMA = "bilqis.c04.capability-result/v3"
SOLVE_REPLAY_SCHEMA = "bilqis.c04.solve-replay/v1"
MAX_CACHED_COMPOSITIONS = 16
MAX_NEURAL_CALLS = 1
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)

