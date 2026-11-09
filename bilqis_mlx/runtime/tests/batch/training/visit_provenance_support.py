"""Frozen C03 visit-record fixture used only to test C02 transport semantics."""
from __future__ import annotations

import hashlib
import json

from bilqis_mlx.runtime.atlas_visit_provenance import BamfVisitProvenance


def c03_visit_record(capability_id: str, *, run_seed: int = 17,
                     generation: int = 0, selection_seed: int = 42,
                     policy_key: str = "p-strong") -> dict:
    payload = {
        "run_identity_sha256": "1" * 64,
        "run_seed": run_seed,
        "generation": generation,
        "accepted_manifest_sha256": "2" * 64,
        "teacher_identity": "3" * 64,
        "teacher_epoch": 0,
        "student_sha256": "4" * 64,
        "selection_seed": selection_seed,
        "cursor": "lesson:7",
        "capability_id": capability_id,
        "policy_key": policy_key,
        "schema": "bilqis.bamf.c03-teacher-visit-identity/v1",
    }
    wire = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {**payload, "visit_id": hashlib.sha256(wire.encode()).hexdigest()}


def visit_provenance(capability_id: str, **kwargs) -> BamfVisitProvenance:
    return BamfVisitProvenance.from_c03_record(
        c03_visit_record(capability_id, **kwargs))


__all__ = ("c03_visit_record", "visit_provenance")
