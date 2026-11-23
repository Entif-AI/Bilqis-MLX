"""Candidate-horizon evidence capture for the persistent BAMF operator."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import time

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.runtime import state
from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar

from .support import (
    EVIDENCE_SCHEMA, PERSISTENCE_SCHEMA, REFERENCE_SCHEMA, _ROLE_FIELDS,
    _SHA256_HEX_LENGTH, _SIDECAR_ROOT, _invalid, _plain, candidate_attempt_id,
    prepare_candidate_evidence_root,
)
from .multifidelity import (
    configure_multifidelity as _configure_multifidelity,
    finalize_multifidelity as _finalize_multifidelity,
    record_multifidelity_rung as _record_multifidelity_rung,
)


class CandidateEvidenceCapture:
    """Buffer speculative step evidence and durably install it once per horizon."""

    def __init__(
            self, run_dir: Path, selection, *, generation: int,
            accepted_manifest_sha256: str, candidate_attempt_ordinal: int,
            parent_optimizer_step: int, introductory: bool | None = None):
        identity = getattr(getattr(selection, "visit", None), "identity", None)
        visit_id = getattr(identity, "visit_id", None)
        policy_key = getattr(identity, "policy_key", None)
        selected_option = getattr(selection, "option_id", None)
        capability = getattr(getattr(selection, "offer", None), "capability_id", None)
        source_seed = getattr(getattr(selection, "offer", None), "source_seed", None)
        release_sha256 = getattr(getattr(selection, "offer", None), "release_sha256", None)
        if (not isinstance(visit_id, str) or not visit_id
                or not isinstance(policy_key, str) or not policy_key
                or not isinstance(selected_option, str) or not selected_option
                or not isinstance(capability, str) or not capability
                or type(source_seed) is not int or source_seed < 0
                or not isinstance(release_sha256, str)
                or len(release_sha256) != _SHA256_HEX_LENGTH
                or any(char not in "0123456789abcdef" for char in release_sha256)
                or type(generation) is not int or generation < 0
                or not isinstance(accepted_manifest_sha256, str)
                or len(accepted_manifest_sha256) != _SHA256_HEX_LENGTH
                or any(char not in "0123456789abcdef"
                       for char in accepted_manifest_sha256)
                or type(candidate_attempt_ordinal) is not int
                or candidate_attempt_ordinal < 1
                or type(parent_optimizer_step) is not int
                or parent_optimizer_step < 0
                or not callable(getattr(identity, "to_record", None))):
            _invalid("BAMF_C16_3_EVIDENCE_SELECTION_INVALID")
        self.run_dir = Path(run_dir)
        self.selected_option = selected_option
        self.attempt_id = candidate_attempt_id(
            generation, accepted_manifest_sha256, visit_id,
            candidate_attempt_ordinal)
        self.proposal = {
            "schema": "bilqis.bamf.c16.3-priority-proposal/v1",
            "attempt_id": self.attempt_id,
            "visit_id": visit_id,
            "teacher_visit": _plain(identity.to_record()),
            "generation": generation,
            "accepted_manifest_sha256": accepted_manifest_sha256,
            "candidate_attempt_ordinal": candidate_attempt_ordinal,
            "parent_optimizer_step": parent_optimizer_step,
            "capability": capability,
            "factory_release_sha256": release_sha256,
            "selected_option": selected_option,
            "selected_policy_key": policy_key,
            "source_seed": source_seed,
            "policy": _plain(getattr(selection, "policy", None)),
        }
        metadata = getattr(selection, 'metadata', None)
        if isinstance(metadata, dict) and 'how_context' in metadata:
            self.proposal['how_context'] = _plain(metadata['how_context'])
            self.proposal['selected_teacher_sha256'] = (
                selection.visit.projection.teacher_state['c03_lineage'][
                    'current_teacher_sha256'])
        self.proposal_id = state._fingerprint(self.proposal)
        self._source_objects = {}
        self._steps = []
        self._finalized = None
        self._learning_course = None
        self._learning_steps = []
        self._learning_missing = False
        self._introductory = introductory
        self._multifidelity = None

    def _object_ref(self, row):
        value = _plain(row)
        digest = state._fingerprint(value)
        existing = self._source_objects.get(digest)
        if existing is not None and existing != value:
            _invalid("BAMF_C16_3_EVIDENCE_OBJECT_COLLISION")
        self._source_objects[digest] = value
        return digest

    def _row_refs(self, rows):
        return [self._object_ref(row) for row in rows]

    def _materialize_delivery(self, release, capability, step, rows, evidence):
        if (type(step) is not int or step < 1
                or not isinstance(capability, str) or not capability
                or capability != self.proposal["capability"]
                or getattr(release, "release_sha256", None)
                != self.proposal["factory_release_sha256"]
                or not isinstance(rows, (tuple, list)) or not rows):
            _invalid("BAMF_C16_3_EVIDENCE_DELIVERY_INVALID")
        if self._steps and step != self._steps[-1]["step"] + 1:
            _invalid("BAMF_C16_3_EVIDENCE_STEP_ORDER_INVALID")
        seed = evidence.get("seed")
        controls = evidence.get("controls", {})
        if type(seed) is not int or seed < 0 or not isinstance(controls, dict):
            _invalid("BAMF_C16_3_EVIDENCE_DELIVERY_INVALID")
        if "delivered_content_sha256" not in controls:
            from bilqis_mlx.factory.teaching import content_digest
            controls = {**controls, "delivered_content_sha256": content_digest(rows)}
        role_ids = {}
        for name, role in _ROLE_FIELDS:
            group = evidence.get(name, ())
            if group is None:
                group = ()
            if not isinstance(group, (tuple, list)):
                _invalid("BAMF_C16_3_EVIDENCE_DELIVERY_INVALID")
            role_ids[role] = {row["id"] for row in group}
            self._row_refs(group)
        source_ids = role_ids["selected_option"]
        delivered = [row for row in rows if row["id"] in source_ids]
        try:
            from bilqis_mlx.diagnostics.teaching import inspect_lesson_step
            course = release.curriculum
            offered = evidence.get("option_rows", ())
            if (not offered or not delivered or
                    self._learning_course is not None
                    and self._learning_course is not course):
                self._learning_missing = True
            elif not self._learning_missing:
                self._learning_course = course
                self._learning_steps.append(inspect_lesson_step(
                    course, capability, list(offered), delivered))
        except (ValueError, TypeError, AttributeError, KeyError, ImportError):
            self._learning_missing = True
        execution = release.execution_plan.capability_map.get(capability)
        teaching_options = getattr(execution, "teaching_option_ids", ())
        if not isinstance(teaching_options, tuple) or not teaching_options:
            _invalid("BAMF_C16_3_EVIDENCE_DELIVERY_INVALID")
        teaching_option = teaching_options[0]
        description = (
            asdict(describe_delivered_teaching(
                release, capability, teaching_option, delivered))
            if delivered else None)
        positions = []
        for row in rows:
            roles = [role for role, ids in role_ids.items() if row["id"] in ids]
            if not roles:
                roles = ["constructed_target"]
            owner = release.execution_plan.capability_map.get(row.get("capability"))
            positions.append({
                "row": self._object_ref(row),
                "roles": roles,
                "provider_id": owner.provider_id if owner is not None else None,
                "provider_implementation_sha256": (
                    owner.provider_implementation_sha256 if owner is not None else None),
            })
        self._steps.append({
            "step": step, "capability": capability, "seed": seed,
            "delivered_teaching": description, "positions": positions,
            "guidance": _plain(evidence.get("guidance")),
            "controls": _plain(controls),
            "mentors": _plain(evidence.get("mentors")),
        })

    def delivery(self, release, capability, step, rows, **evidence):
        self._materialize_delivery(release, capability, step, rows, evidence)

    def learning_methodology(self) -> tuple[dict, ...]:
        """Advisory only; never included in the C16.3 hashed custody payload."""
        from bilqis_mlx.diagnostics.signals import DiagnosticStatus, LearningSignal
        status = DiagnosticStatus.NOT_MEASURED
        result = []
        signals = (
            LearningSignal.DISCONNECTED_PREREQUISITES,
            LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY,
        )
        try:
            if (not self._learning_missing and self._learning_steps and
                    self._learning_course is not None):
                from bilqis_mlx.diagnostics.teaching import diagnose_teaching_visit
                findings = diagnose_teaching_visit(
                    self._learning_course, self.proposal["capability"],
                    tuple(self._learning_steps), introductory=self._introductory)
                return tuple({
                    "signal": item.signal.value, "status": item.status.value,
                    "note": item.note, "evidence_count": item.evidence_count,
                } for item in findings)
        except (ValueError, TypeError, AttributeError, KeyError):
            pass
        for signal in signals:
            result.append({
                "signal": signal.value, "status": status.value,
                "note": "Source-backed lesson structure unavailable",
                "evidence_count": 0,
            })
        return tuple(result)

    def configure_multifidelity(self, **kwargs):
        return _configure_multifidelity(self, **kwargs)

    def record_multifidelity_rung(self, **kwargs):
        return _record_multifidelity_rung(self, **kwargs)

    def finalize(self, *, accepted: bool, decision: dict):
        if type(accepted) is not bool or not isinstance(decision, dict) or not decision:
            _invalid("BAMF_C16_3_EVIDENCE_OUTCOME_INVALID")
        if not self._steps:
            _invalid("BAMF_C16_3_EVIDENCE_EMPTY_HORIZON")
        outcome = {"accepted": accepted, "decision": _plain(decision)}
        multifidelity = _finalize_multifidelity(self, accepted)
        payload = {
            "schema": EVIDENCE_SCHEMA,
            "attempt_id": self.attempt_id,
            "proposal_id": self.proposal_id,
            "proposal": self.proposal,
            "source_objects": dict(sorted(self._source_objects.items())),
            "steps": list(self._steps),
            "outcome": outcome,
            **({"multifidelity_shadow": multifidelity}
               if multifidelity is not None else {}),
        }
        if self._finalized is not None:
            if self._finalized[0] != state._fingerprint(payload):
                _invalid("BAMF_C16_3_EVIDENCE_FINALIZATION_DRIFT")
            return self._finalized[1]

        digest = state._fingerprint(payload)
        prepare_candidate_evidence_root(self.run_dir)
        path = self.run_dir / _SIDECAR_ROOT / f"{digest}.json"
        if not path.parent.is_dir():
            _invalid("BAMF_C16_3_EVIDENCE_ROOT_INVALID")
        existed = path.is_file()
        started = time.perf_counter()
        reference = store_sidecar(self.run_dir, payload)
        elapsed = max(0.0, time.perf_counter() - started)
        if reference.get("sha256") != digest:
            _invalid("BAMF_C16_3_EVIDENCE_REFERENCE_DRIFT")
        persistence = {
            "schema": PERSISTENCE_SCHEMA,
            "bytes_written": 0 if existed else path.stat().st_size,
            "file_fsyncs": 0 if existed else 1,
            "directory_fsyncs": 0 if existed else 1,
            "evidence_objects": 0 if existed else 1,
            "logical_records": len(self._steps) + 2,
            "unique_source_objects": len(self._source_objects),
            "delivery_records": len(self._steps),
            "persistence_seconds": elapsed,
        }
        receipt = {
            "schema": REFERENCE_SCHEMA,
            "attempt_id": self.attempt_id,
            "proposal_id": self.proposal_id,
            "object": reference,
            "persistence": persistence,
        }
        self._finalized = (digest, receipt)
        return receipt


__all__ = ("CandidateEvidenceCapture",)
