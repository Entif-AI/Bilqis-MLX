"""Machine-enforced FOUNDATION_ACQUISITION evidence-policy checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


DEVELOPMENTAL_POLICY = Path("docs/specifications/developmental_evidence_policy.json")
RELEASE_BOUNDARY_OVERRIDES = Path("docs/tasks/bamf-0.2/release-boundary-overrides.json")
FOUNDATION_POLICY_MARKER = "FOUNDATION_EVIDENCE_POLICY_ACTIVE"
FOUNDATION_POLICY_DOCS = (
    Path("README.md"),
    Path("AGENTS.md"),
    Path("docs/specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md"),
    Path("docs/architecture/BAMF_0_2.md"),
    Path("docs/tasks/bamf-0.2/issues/A08.md"),
    Path("docs/tasks/bamf-0.2/issues/C01.md"),
    Path("docs/tasks/bamf-0.2/issues/C02.md"),
    Path("docs/tasks/bamf-0.2/issues/C04.md"),
    Path("docs/tasks/bamf-0.2/issues/C05.md"),
    Path("docs/tasks/bamf-0.2/issues/C13.md"),
    Path("docs/tasks/bamf-0.2/issues/C14.md"),
    Path("docs/tasks/bamf-0.2/issues/C16.md"),
)
PREMATURE_FOUNDATION_GATES = (
    "strictly improved fresh target",
    "strictly improved fresh complete-solver target score",
    "scoring fresh seeds64..127",
    "Score target improvement on independently held-out",
    "### 3.6 Generalization is part of graduation",
)


def _developmental_evidence_expected() -> dict[tuple[str, ...], object]:
    return {
        ("schema",): "bilqis.developmental-evidence-policy/v1",
        ("current_stage",): "FOUNDATION_ACQUISITION",
        ("generalization_status",): "MEASURE_ONLY",
        ("fixed_generalization_gate_authority",): "EXPLICIT_HUMAN_ADMISSION",
        ("policy_authority", "foundation_acquisition"): ["ADR-133", "ADR-134", "ADR-157"],
        ("policy_authority", "retention_recovery_clarification"): "ADR-157",
        ("current_acceptance", "teacher_forced_gold_allowed"): True,
        ("current_acceptance", "same_specimen_replay_allowed"): True,
        ("current_acceptance", "exact_memorization_counts_as_learning"): True,
        ("current_acceptance", "cache_memoization_retrieval_counts_as_learning"): True,
        ("current_acceptance", "retained_taught_semantics_count_as_learning"): True,
        ("current_acceptance", "held_out_required"): False,
        ("current_acceptance", "independent_source_family_required"): False,
        ("current_acceptance", "fresh_episode_required"): False,
        ("current_acceptance", "novel_composition_required"): False,
        ("current_acceptance", "allowed_evidence_kinds"): [
            "TEACHER_FORCED_ACQUISITION",
            "EXACT_TAUGHT_RECALL",
            "TAUGHT_COMPOSITION_REPLICATION",
        ],
        ("independent_assessment", "source_oracle_independence_required"): True,
        ("independent_assessment", "learner_answer_gold_input_forbidden"): True,
        ("independent_assessment", "solver_answer_gold_input_forbidden"): True,
        ("independent_assessment", "scorer_source_authorized_gold_required"): True,
        ("independent_assessment", "scoring_must_not_inject_gold_into_solver"): True,
        ("independent_assessment", "taught_semantics_eligible"): True,
        ("independent_assessment", "previously_shown_specimens_eligible"): True,
        ("independent_assessment", "zero_semantic_overlap_required"): False,
        ("independent_assessment", "zero_specimen_overlap_required"): False,
        ("independent_assessment", "zero_source_family_overlap_required"): False,
        ("independent_assessment", "zero_episode_overlap_required"): False,
        ("developmental_sequence", "teach_semantics_before_generalization_expectation"): True,
        ("developmental_sequence", "untaught_semantics_generalization_status"): "MEASURE_ONLY",
        ("alpha_advancement", "basis"): "CURRENT_EARNED_COMPLEXITY_SUCCESS_RATIO",
        ("alpha_advancement", "previously_shown_examples_count"): True,
        ("alpha_advancement", "held_out_required"): False,
        ("alpha_advancement", "novelty_required"): False,
        ("alpha_advancement", "pool_growth"): "INCREMENTAL_OR_LOGARITHMIC",
        ("alpha_advancement", "complexity_growth"): "EARNED",
        ("candidate_retention", "immediate_target_gain_required"): False,
        ("candidate_retention", "protected_regression_checks_required"): True,
        ("candidate_retention", "no_gain_strategy_retirement_remains_teacher_owned"): True,
        ("candidate_retention", "primary_product_metric"):
            "INDEPENDENTLY_VERIFIED_RETAINED_TAUGHT_COMPETENCE_PER_WALL_CLOCK_MINUTE",
        ("candidate_retention", "generalization_metric_is_separate"): True,
        ("novelty_measurement", "required"): True,
        ("novelty_measurement", "authorizing"): False,
        ("novelty_measurement", "may_veto_advancement"): False,
        ("novelty_measurement", "record_pass_failure_ratios"): True,
        ("novelty_measurement", "record_breakdown_frontier"): True,
        ("novelty_measurement", "axes"): [
            "SURFACE_IDENTITY",
            "ROLE_BINDING",
            "RELATION_POLARITY",
            "COMPOSITION_DEPTH",
            "DISTRACTOR_LOAD",
            "SEMANTIC_DISTANCE",
        ],
        ("future_fixed_gate", "requires_explicit_human_admission"): True,
    }


def _developmental_evidence_policy(root: Path) -> tuple[str, ...]:
    problems = []
    path = root / DEVELOPMENTAL_POLICY
    if not path.is_file():
        return ("DEVELOPMENTAL_EVIDENCE_POLICY_MISSING",)
    try:
        policy = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return ("DEVELOPMENTAL_EVIDENCE_POLICY_INVALID",)
    for keys, value in _developmental_evidence_expected().items():
        actual = policy
        for key in keys:
            actual = actual.get(key) if isinstance(actual, dict) else None
        if actual != value:
            problems.append(
                "DEVELOPMENTAL_EVIDENCE_POLICY_DRIFT:"
                + ".".join(keys)
                + f":expected={value!r}:actual={actual!r}")
    problems.extend(_developmental_policy_docs(root))
    owner = root / "bilqis_mlx/runtime/_capability/factory/factory_retention_owner.py"
    if not owner.is_file():
        problems.append("FACTORY_RETENTION_OWNER_MISSING")
    elif ("CURRENT_EVIDENCE_STAGE = EvidenceStage.FOUNDATION_ACQUISITION"
          not in owner.read_text()):
        problems.append("FACTORY_RETENTION_OWNER_EVIDENCE_STAGE_DRIFT")
    evaluation = root / "bilqis_mlx/runtime/_capability/capability_evaluation.py"
    if not evaluation.is_file():
        problems.append("CAPABILITY_EVALUATION_MISSING")
    else:
        source = evaluation.read_text()
        if ("evidence_stage: EvidenceStage = EvidenceStage.FOUNDATION_ACQUISITION"
                not in source):
            problems.append("CAPABILITY_EVALUATION_DEFAULT_STAGE_DRIFT")
        if 'STRICT_GENERALIZATION = "STRICT_GENERALIZATION"' not in source:
            problems.append("STRICT_GENERALIZATION_OPT_IN_MISSING")
    return tuple(problems)


def _developmental_policy_docs(root: Path) -> tuple[str, ...]:
    problems = []
    for relative in FOUNDATION_POLICY_DOCS:
        document = root / relative
        if not document.is_file():
            problems.append(f"{relative} DEVELOPMENTAL_POLICY_DOC_MISSING")
            continue
        text = document.read_text()
        if (FOUNDATION_POLICY_MARKER not in text
                and not _release_boundary_override_matches(root, relative, text)):
            problems.append(f"{relative} DEVELOPMENTAL_POLICY_MARKER_MISSING")
        for phrase in PREMATURE_FOUNDATION_GATES:
            if phrase in text:
                problems.append(
                    f"{relative} PREMATURE_FOUNDATION_GENERALIZATION_GATE:{phrase}")
    return tuple(problems)


def _release_boundary_override_matches(root: Path, relative: Path, text: str) -> bool:
    """Accept a marker-free owner rewrite only when its audited live hash is exact."""
    if "issues" not in relative.parts:
        return False
    path = root / RELEASE_BOUNDARY_OVERRIDES
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text())
        if payload.get("schema") != "bilqis.bamf.release-boundary-overrides/v1":
            return False
        digest = hashlib.sha256(text.encode()).hexdigest()
        return any(
            row.get("key") == relative.stem and row.get("live_body_sha256") == digest
            for row in payload.get("entries", ()) if isinstance(row, dict)
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False
