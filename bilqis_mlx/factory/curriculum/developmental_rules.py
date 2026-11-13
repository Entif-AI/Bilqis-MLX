"""Immutable C14 grade-neutral rule policy over the existing recursive planner."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import json

from bilqis_mlx.errors import ErrorBus, FACTORY
from .developmental_program import BamfDevelopmentalProgram
from .developmental_stage import (
    DevelopmentalLearnerState, DevelopmentalSourceCoverage, StageIntent,
)


SCHEMA = "bilqis.bamf.domain-rules/v1"
DEFAULT_RULE_RESOURCE = "bamf-domain-rules-v1.json"
POLICY_VERSION = "c14-grade-neutral-v1"
GRADE_INTRODUCTION = "FACTORY_RELEASE_DATA_OPERATION"
CROSS_DOMAIN_BLOCKING = "TYPED_PREREQUISITE_EDGES_ONLY"
FAMILY_IDS = (
    "boolean_composition",
    "morphology_composition",
    "morphology_decomposition",
    "numeric_composition",
    "positive_identity",
    "qualified_world_model",
    "released_transformations",
    "scope_modality_time",
    "source_attested_relation",
    "typed_role_binding",
)
SHARED_CONTRACTS = (
    "SOURCE_QUALIFIED_PREREQUISITES",
    "CURRENT_EVIDENCE_REQUIRED",
    "FAMILY_OWNED_TEACHING_ASSESSMENT",
    "GRADE_NEUTRAL_PROMOTION_DEBT",
    "FACTORY_RELEASE_ADMISSION",
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(FACTORY.SEMANTIC_RULE.INVALID, reason=reason)


@dataclass(frozen=True)
class DevelopmentalRuleManifest:
    schema: str
    policy_version: str
    family_ids: tuple[str, ...]
    shared_contracts: tuple[str, ...]
    grade_introduction: str
    cross_domain_blocking: str
    named_grade_priority: bool
    named_grade_debt_exception: bool

    def __post_init__(self) -> None:
        if (self.schema != SCHEMA
                or self.policy_version != POLICY_VERSION
                or self.family_ids != FAMILY_IDS
                or self.shared_contracts != SHARED_CONTRACTS
                or self.grade_introduction != GRADE_INTRODUCTION
                or self.cross_domain_blocking != CROSS_DOMAIN_BLOCKING
                or type(self.named_grade_priority) is not bool
                or type(self.named_grade_debt_exception) is not bool
                or self.named_grade_priority or self.named_grade_debt_exception):
            _fail("DEVELOPMENTAL_DOMAIN_RULE_MANIFEST_INVALID")

    def require_family(self, family_id: str) -> None:
        if family_id not in self.family_ids:
            _fail("DEVELOPMENTAL_DOMAIN_RULE_FAMILY_UNCOVERED")


@dataclass(frozen=True)
class DomainSuccessionIntent:
    stage: StageIntent
    rule_policy_version: str
    selected_rule_family_ids: tuple[str, ...]
    shared_contracts: tuple[str, ...]
    grade_introduction: str = GRADE_INTRODUCTION
    cross_domain_blocking: str = CROSS_DOMAIN_BLOCKING
    named_grade_priority: bool = False
    named_grade_debt_exception: bool = False

    def __post_init__(self) -> None:
        if (type(self.stage) is not StageIntent
                or not isinstance(self.rule_policy_version, str)
                or not self.rule_policy_version
                or type(self.selected_rule_family_ids) is not tuple
                or self.selected_rule_family_ids
                   != tuple(sorted(set(self.selected_rule_family_ids)))
                or self.shared_contracts != SHARED_CONTRACTS
                or self.grade_introduction != GRADE_INTRODUCTION
                or self.cross_domain_blocking != CROSS_DOMAIN_BLOCKING
                or self.named_grade_priority or self.named_grade_debt_exception):
            _fail("DEVELOPMENTAL_DOMAIN_SUCCESSION_INVALID")


def load_developmental_rule_manifest() -> DevelopmentalRuleManifest:
    """Load the immutable C14 domain policy packaged with the Factory."""
    try:
        payload = json.loads(resources.files(__package__).joinpath(
            DEFAULT_RULE_RESOURCE).read_text(encoding="utf-8"))
    except (OSError, TypeError, UnicodeError, json.JSONDecodeError):
        _fail("DEVELOPMENTAL_DOMAIN_RULE_MANIFEST_READ_INVALID")
    expected = {
        "schema", "policy_version", "family_ids", "shared_contracts",
        "grade_introduction", "cross_domain_blocking", "named_grade_priority",
        "named_grade_debt_exception",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        _fail("DEVELOPMENTAL_DOMAIN_RULE_MANIFEST_FIELDS_INVALID")
    for key in ("family_ids", "shared_contracts"):
        if type(payload[key]) is not list:
            _fail("DEVELOPMENTAL_DOMAIN_RULE_MANIFEST_INVALID")
    return DevelopmentalRuleManifest(
        payload["schema"], payload["policy_version"], tuple(payload["family_ids"]),
        tuple(payload["shared_contracts"]), payload["grade_introduction"],
        payload["cross_domain_blocking"], payload["named_grade_priority"],
        payload["named_grade_debt_exception"],
    )


def resolve_domain_succession(
    program: BamfDevelopmentalProgram,
    source_coverage: DevelopmentalSourceCoverage,
    learner_state: DevelopmentalLearnerState,
    rules: DevelopmentalRuleManifest,
) -> DomainSuccessionIntent:
    """Reuse the existing pure planner and bind its selected families to C14 policy."""
    if type(program) is not BamfDevelopmentalProgram or type(rules) is not DevelopmentalRuleManifest:
        _fail("DEVELOPMENTAL_DOMAIN_SUCCESSION_INPUT_INVALID")
    if rules != load_developmental_rule_manifest():
        _fail("DEVELOPMENTAL_DOMAIN_RULE_MANIFEST_NONCANONICAL")
    stage = program.resolve_training_stage(source_coverage, learner_state)
    families = tuple(sorted(stage.selected_family_ids))
    for family_id in families:
        rules.require_family(family_id)
    return DomainSuccessionIntent(
        stage, rules.policy_version, families, rules.shared_contracts)
