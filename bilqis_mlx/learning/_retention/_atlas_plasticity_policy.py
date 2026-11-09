"""Retained plasticity cadence policy and accepted-candidate transitions."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning._atlas_plasticity_base import (
    IdentityRowAge, _valid_ages, advance_accepted_row_ages,
)
from bilqis_mlx.learning._atlas_plasticity_transition import (
    ACCEPTED_FAST_INTERVAL, ADAPTIVE_MODE, FAST_UPDATE, FOUNDATION_MODE, FULL_UPDATE,
    POLICY_STATE_SCHEMA, POLICY_VERSION, TRANSITIONED_POLICY_STATE_SCHEMA,
    TRANSITIONED_POLICY_VERSION, ModeTransition,
    _AGE_RECORD_FIELDS, _POLICY_RECORD_FIELDS, _POLICY_RECORD_FIELDS_V2,
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

@dataclass(frozen=True)
class PlasticityPolicy:
    """Detached cadence state; the retained-generation owner persists this record.

    Fresh construction starts in FOUNDATION. Loading ADAPTIVE is a cold-reader
    operation, not authority to transition a running student. B09.3 owns the
    promotion-receipt transition; no transition is inferred here from grades.
    """

    mode: str = FOUNDATION_MODE
    accepted_fast_since_full: int = 0
    row_ages: tuple[IdentityRowAge, ...] = ()
    policy_version: str = POLICY_VERSION
    schema_version: str = POLICY_STATE_SCHEMA
    mode_transition: ModeTransition | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        legacy = (self.policy_version == POLICY_VERSION
                  and self.schema_version == POLICY_STATE_SCHEMA)
        transitioned = (
            self.policy_version == TRANSITIONED_POLICY_VERSION
            and self.schema_version == TRANSITIONED_POLICY_STATE_SCHEMA)
        if (type(self.mode) is not str or self.mode not in (FOUNDATION_MODE, ADAPTIVE_MODE)
                or type(self.accepted_fast_since_full) is not int
                or self.accepted_fast_since_full < 0
                or (self.mode == FOUNDATION_MODE and self.accepted_fast_since_full != 0)
                or not _valid_ages(self.row_ages)
                or not (legacy or transitioned)
                or (legacy and self.mode_transition is not None)
                or (transitioned and (
                    self.mode != ADAPTIVE_MODE
                    or type(self.mode_transition) is not ModeTransition))):
            _invalid()
        for row in self.row_ages:
            row.__post_init__()
        if self.mode_transition is not None:
            self.mode_transition.__post_init__()

    def to_record(self) -> dict:
        """Exact JSON-compatible state, without checkpoint/publication authority."""
        self.validate()
        result = {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "mode": self.mode,
            "accepted_fast_since_full": self.accepted_fast_since_full,
            "row_ages": [{"bank_index": row.bank_index, "row_index": row.row_index,
                          "accepted_age": row.accepted_age, "schema_version": row.schema_version}
                         for row in self.row_ages],
        }
        if self.schema_version == TRANSITIONED_POLICY_STATE_SCHEMA:
            result["mode_transition"] = self.mode_transition.to_record()
        return result

    @classmethod
    def from_record(cls, record: object) -> "PlasticityPolicy":
        """Reject missing, extra or incompatible fields rather than infer clocks."""
        if type(record) is not dict:
            _invalid()
        fields = (_POLICY_RECORD_FIELDS
                  if record.get("schema_version") == POLICY_STATE_SCHEMA
                  else _POLICY_RECORD_FIELDS_V2
                  if record.get("schema_version") == TRANSITIONED_POLICY_STATE_SCHEMA
                  else frozenset())
        if (not fields or set(record) != fields
                or type(record["row_ages"]) is not list
                or any(type(row) is not dict or set(row) != _AGE_RECORD_FIELDS
                       for row in record["row_ages"])):
            _invalid()
        transition = (None if "mode_transition" not in record else
                      ModeTransition.from_record(record["mode_transition"]))
        return cls(mode=record["mode"], accepted_fast_since_full=record["accepted_fast_since_full"],
                   row_ages=tuple(IdentityRowAge(**row) for row in record["row_ages"]),
                   policy_version=record["policy_version"], schema_version=record["schema_version"],
                   mode_transition=transition)


def _mode_transition_from_receipt(receipt) -> ModeTransition:
    return ModeTransition(
        run_id=receipt.run_id,
        parent_generation=receipt.parent_generation,
        candidate_generation=receipt.candidate_generation,
        candidate_identity_sha256=receipt.candidate_identity_sha256,
        optimizer_step=receipt.optimizer_step,
        decision_sha256=receipt.decision_sha256,
        initial_factory_release_sha256=receipt.initial_factory_release_sha256,
        foundation_capability_ids=receipt.foundation_capability_ids,
        promotion_evidence_sha256=receipt.promotion_evidence_sha256,
        assessment_epoch=receipt.assessment_epoch,
        outcome=receipt.outcome,
        carried_debt=receipt.carried_debt,
        promotion_receipt_sha256=receipt.digest,
    )


def apply_promotion_transition(
        policy: PlasticityPolicy, receipt) -> PlasticityPolicy:
    """Consume one live C05 receipt and persist the one-way cadence transition."""
    from bilqis_mlx.runtime.plasticity_promotion import (
        require_accepted_promotion_transition,
    )
    if type(policy) is not PlasticityPolicy:
        _invalid()
    require_accepted_promotion_transition(receipt)
    expected = _mode_transition_from_receipt(receipt)
    if policy.schema_version == TRANSITIONED_POLICY_STATE_SCHEMA:
        if policy.mode_transition != expected:
            _invalid()
        return policy
    if (policy.schema_version != POLICY_STATE_SCHEMA
            or policy.policy_version != POLICY_VERSION
            or policy.mode != FOUNDATION_MODE
            or policy.mode_transition is not None):
        _invalid()
    return PlasticityPolicy(
        mode=ADAPTIVE_MODE,
        accepted_fast_since_full=0,
        row_ages=policy.row_ages,
        policy_version=TRANSITIONED_POLICY_VERSION,
        schema_version=TRANSITIONED_POLICY_STATE_SCHEMA,
        mode_transition=expected,
    )


def next_update_mode(state: PlasticityPolicy, *, teacher_requests_full: bool) -> str:
    """Choose eligibility only; targets, rate and pedagogy stay with the teacher."""
    if type(state) is not PlasticityPolicy or type(teacher_requests_full) is not bool:
        _invalid()
    state.validate()
    if (state.mode == FOUNDATION_MODE or teacher_requests_full
            or state.accepted_fast_since_full >= ACCEPTED_FAST_INTERVAL):
        return FULL_UPDATE
    return FAST_UPDATE


def advance_candidate_policy(
    parent: PlasticityPolicy, *, teacher_requests_full: bool, accepted: bool,
    participating_rows: tuple[tuple[int, int], ...],
) -> PlasticityPolicy:
    """Compute a retained-candidate proposal, without deciding or publishing it.

    The existing acceptance owner supplies accepted and the deduplicated union
    of actual masked-step rows. Rejection preserves the parent object. A single
    acceptance advances each involved row once, irrespective of internal steps.
    """
    update_mode = next_update_mode(parent, teacher_requests_full=teacher_requests_full)
    ages = advance_accepted_row_ages(parent.row_ages, participating_rows, accepted=accepted)
    if not accepted:
        return parent
    counter = (parent.accepted_fast_since_full + 1
               if parent.mode == ADAPTIVE_MODE and update_mode == FAST_UPDATE else 0)
    return PlasticityPolicy(
        mode=parent.mode, accepted_fast_since_full=counter, row_ages=ages,
        policy_version=parent.policy_version,
        schema_version=parent.schema_version,
        mode_transition=parent.mode_transition)
