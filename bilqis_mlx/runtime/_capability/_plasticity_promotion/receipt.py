from __future__ import annotations

from dataclasses import dataclass

from .common import digest, invalid, is_digest


RECEIPT_SCHEMA = "bilqis.mlx.accepted-promotion-transition/v1"
_OUTCOMES = frozenset({"PROMOTED", "PROMOTED_WITH_DEBT"})
_FIELDS = (
    "run_id", "parent_generation", "candidate_generation",
    "parent_manifest_sha256", "parent_candidate_identity_sha256",
    "candidate_identity_sha256", "optimizer_step", "decision_sha256",
    "initial_factory_release_sha256", "foundation_capability_ids",
    "promotion_state_generations", "promotion_evidence_sha256",
    "assessment_epoch", "outcome", "carried_debt", "schema_version",
)


def _new_receipt_owner():
    issued = {}

    def require(value):
        if issued.get(id(value)) is not value:
            invalid()
        return value

    def issue(values):
        receipt = object.__new__(AcceptedPromotionTransitionReceipt)
        for name, value in values:
            object.__setattr__(receipt, name, value)
        issued[id(receipt)] = receipt
        receipt.__post_init__()
        return receipt

    return require, issue


@dataclass(frozen=True)
class AcceptedPromotionTransitionReceipt:
    """Live C05 capability proving one current-generation promotion boundary."""

    run_id: str
    parent_generation: int
    candidate_generation: int
    parent_manifest_sha256: str
    parent_candidate_identity_sha256: str
    candidate_identity_sha256: str
    optimizer_step: int
    decision_sha256: str
    initial_factory_release_sha256: str
    foundation_capability_ids: tuple[str, ...]
    promotion_state_generations: tuple[int, ...]
    promotion_evidence_sha256: str
    assessment_epoch: int
    outcome: str
    carried_debt: tuple[str, ...]
    schema_version: str = RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        _require_accepted_promotion_transition(self)
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.parent_generation) is not int
                or self.parent_generation < 0
                or self.candidate_generation != self.parent_generation + 1
                or any(not is_digest(value) for value in (
                    self.parent_manifest_sha256,
                    self.parent_candidate_identity_sha256,
                    self.candidate_identity_sha256, self.decision_sha256,
                    self.initial_factory_release_sha256,
                    self.promotion_evidence_sha256))
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or type(self.foundation_capability_ids) is not tuple
                or not self.foundation_capability_ids
                or len(set(self.foundation_capability_ids))
                != len(self.foundation_capability_ids)
                or any(not isinstance(item, str) or not item
                       for item in self.foundation_capability_ids)
                or type(self.promotion_state_generations) is not tuple
                or not self.promotion_state_generations
                or any(type(item) is not int or item < 0
                       for item in self.promotion_state_generations)
                or tuple(sorted(set(self.promotion_state_generations)))
                != self.promotion_state_generations
                or type(self.assessment_epoch) is not int
                or self.assessment_epoch < 0
                or self.outcome not in _OUTCOMES
                or type(self.carried_debt) is not tuple
                or len(set(self.carried_debt)) != len(self.carried_debt)
                or any(not isinstance(item, str) or not item
                       for item in self.carried_debt)
                or (self.outcome == "PROMOTED" and self.carried_debt)
                or self.schema_version != RECEIPT_SCHEMA):
            invalid()

    def _record(self) -> dict:
        return {
            "run_id": self.run_id,
            "parent_generation": self.parent_generation,
            "candidate_generation": self.candidate_generation,
            "parent_manifest_sha256": self.parent_manifest_sha256,
            "parent_candidate_identity_sha256": self.parent_candidate_identity_sha256,
            "candidate_identity_sha256": self.candidate_identity_sha256,
            "optimizer_step": self.optimizer_step,
            "decision_sha256": self.decision_sha256,
            "initial_factory_release_sha256": self.initial_factory_release_sha256,
            "foundation_capability_ids": list(self.foundation_capability_ids),
            "promotion_state_generations": list(self.promotion_state_generations),
            "promotion_evidence_sha256": self.promotion_evidence_sha256,
            "assessment_epoch": self.assessment_epoch,
            "outcome": self.outcome,
            "carried_debt": list(self.carried_debt),
            "schema_version": self.schema_version,
        }

    @property
    def digest(self) -> str:
        return digest(self._record())

    def to_record(self) -> dict:
        return {**self._record(), "receipt_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "ParsedPromotionTransitionReceipt":
        if (not isinstance(record, dict)
                or set(record) != set(_FIELDS) | {"receipt_sha256"}
                or not isinstance(record["foundation_capability_ids"], list)
                or not isinstance(record["promotion_state_generations"], list)
                or not isinstance(record["carried_debt"], list)):
            invalid()
        payload = {name: record[name] for name in _FIELDS}
        if record["receipt_sha256"] != digest(payload):
            invalid()
        return ParsedPromotionTransitionReceipt(payload)


@dataclass(frozen=True)
class ParsedPromotionTransitionReceipt:
    """Validated historical receipt bytes with no live issuance capability."""
    fields: dict

    @property
    def digest(self) -> str:
        return digest({name: self.fields[name] for name in _FIELDS})

    def to_record(self) -> dict:
        return {**self.fields, "receipt_sha256": self.digest}


_require_accepted_promotion_transition, _raw_issue_receipt = _new_receipt_owner()


def _bind_receipt_issuer(raw_issue):
    def issue_accepted_promotion_transition(run_dir, retained_state, decision):
        """Mint only from the C05-owned validated immutable-evidence path."""
        from .issuance import validated_promotion_transition_fields
        return raw_issue(
            validated_promotion_transition_fields(run_dir, retained_state, decision))
    return issue_accepted_promotion_transition


issue_accepted_promotion_transition = _bind_receipt_issuer(_raw_issue_receipt)


del _raw_issue_receipt
del _bind_receipt_issuer


def require_accepted_promotion_transition(value) -> AcceptedPromotionTransitionReceipt:
    if type(value) is not AcceptedPromotionTransitionReceipt:
        invalid()
    _require_accepted_promotion_transition(value)
    value.__post_init__()
    return value
