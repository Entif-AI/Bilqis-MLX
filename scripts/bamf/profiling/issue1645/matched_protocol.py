"""Prepare and compare immutable experimental intents; never launch training."""
import argparse
import json
from pathlib import Path
from types import MappingProxyType

from scripts.bamf.profiling.issue1645.reservation import (
    digest, require, verify_reservation,
)

MECHANISMS = MappingProxyType({
    "reservation": ("uniform_support", "protected_reserved_support"),
    "allocation": ("fixed_reservation", "evidence_weighted_reservation"),
    "distributed_rehearsal": ("contiguous_support", "distributed_support"),
    "co_observation": ("independent_source_worlds", "source_admitted_shared_world"),
    "epsilon": ("unchanged_epsilon", "output_only_epsilon"),
    "attenuation": ("unmodified_displacement", "conflict_attenuation"),
    "distillation": ("no_adviser_guidance", "source_authorized_guidance"),
    "attainability": ("sequential_targets", "joint_balanced_targets"),
})

MATCHED_FIELDS = (
    "reservation_sha256", "bindings", "tensor_sha256", "teacher_sha256",
    "training_source_sha256", "training_seed", "exam_seed", "exam_each",
    "visit_horizon", "primary_rows", "support_rows", "optimizer_policy_sha256",
    "observer_mode", "prewarm_mode", "wall_seconds", "max_seconds",
    "exam_max_seconds", "worker_count",
)

REQUIRED_EVIDENCE = MappingProxyType({
    "reservation": "source_complete_groups_and_exclusion",
    "allocation": "authenticated_same_scope_negative_archetypes",
    "distributed_rehearsal": "equal_horizon_delivery_budget",
    "co_observation": "source_admitted_shared_worlds",
    "epsilon": "measured_output_displacement_and_loss",
    "attenuation": "measured_displacement_prediction_fidelity",
    "distillation": "authorized_adviser_and_actual_guidance",
    "attainability": "source_valid_joint_allocation",
})


def prepare_pair(reservation, common, mechanism, evidence):
    """Record a decision candidate, never mint approval or an issued exam."""
    verify_reservation(reservation)
    require(mechanism in MECHANISMS, "unknown mechanism")
    require(set(common) == set(MATCHED_FIELDS), "incomplete or extra common bindings")
    require(common["bindings"] == reservation["bindings"], "source mismatch")
    require(common["reservation_sha256"] == reservation["reservation_sha256"],
            "reservation mismatch")
    require(common["exam_each"] == 12, "unbalanced examination scope")
    require(common["worker_count"] == 1, "multiple neural lanes")
    for field in ("training_seed", "exam_seed", "visit_horizon", "primary_rows",
                  "support_rows", "wall_seconds", "max_seconds", "exam_max_seconds"):
        require(type(common[field]) is int and common[field] > 0, "invalid budget")
    require(common["wall_seconds"] <= common["max_seconds"] <= 480
            and common["exam_max_seconds"] <= 300, "outside proposed arm budget")
    require(all(common[field] is not None for field in MATCHED_FIELDS), "missing binding")
    control, treatment = MECHANISMS[mechanism]
    evidence_key = REQUIRED_EVIDENCE[mechanism]
    payload = {
        "schema": "bamf.research_matched_intent.v1",
        "status": "PREPARED_NOT_APPROVED_NOT_LAUNCHED",
        "mechanism": mechanism,
        "common": common,
        "control": control,
        "treatment": treatment,
        "required_evidence": evidence_key,
        "evidence_reference": evidence.get(evidence_key),
        "launch_authorized": False,
    }
    return {**payload, "pair_sha256": digest(payload)}


def validate_comparison(pair, control, treatment):
    body = {k: v for k, v in pair.items() if k != "pair_sha256"}
    require(digest(body) == pair["pair_sha256"], "pair digest mismatch")
    for arm, role in ((control, "control"), (treatment, "treatment")):
        require(arm["common"] == pair["common"], "unmatched common arm bindings")
        require(arm["mechanism"] == pair[role], "wrong treatment identity")
        require(arm["exclusion_enforced"] is True, "exclusion not enforced")
        require(arm["exam_count"] == 72, "partial exam")
        require(arm["actual_wall_seconds"] > 0, "invalid elapsed time")
    require(pair["evidence_reference"], "mechanism prerequisite missing")
    if pair["mechanism"] == "distillation":
        require(control["actual_guidance_steps"] == 0
                and treatment["actual_guidance_steps"] > 0, "guidance not realized")
    return {"pair_sha256": pair["pair_sha256"], "matched_bindings": True,
            "control_retained_gain_per_minute": 60 * control["retained_gain"] / control["actual_wall_seconds"],
            "treatment_retained_gain_per_minute": 60 * treatment["retained_gain"] / treatment["actual_wall_seconds"],
            "certification_granted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reservation", type=Path)
    parser.add_argument("common", type=Path)
    parser.add_argument("mechanism", choices=MECHANISMS)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text()) if args.evidence else {}
    print(json.dumps(prepare_pair(json.loads(args.reservation.read_text()),
                                  json.loads(args.common.read_text()),
                                  args.mechanism, evidence), indent=2))


if __name__ == "__main__":
    main()
