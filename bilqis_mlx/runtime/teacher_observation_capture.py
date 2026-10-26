"""Evidence-only joins from selected teaching through durable candidate publication."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from ..errors import ErrorBus, SCHOOL
from ..factory.teaching import describe_delivered_teaching, content_digest
from . import state

SCHEMA = "bilqis.factory.teacher-observation/v1"
PROPOSAL_SCHEMA = "bilqis.factory.teacher-proposal/v1"
EPOCH_SCHEMA = "bilqis.factory.teacher-evidence-epoch/v1"
SIDECAR_ROOT = "teacher-observations/objects"


def _plain(value):
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_plain(item) for item in sorted(value)]
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _sidecar_path(run_dir, relative):
    path = Path(run_dir).resolve()
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
    return path


def store_sidecar(run_dir, payload):
    payload = _plain(payload)
    digest = state._fingerprint(payload)
    reference = {"sha256": digest, "file": f"{SIDECAR_ROOT}/{digest}.json"}
    path = _sidecar_path(run_dir, reference["file"])
    if path.exists():
        read_sidecar(run_dir, reference)
    else:
        state._durable_json(path, payload)
    return reference


def read_sidecar(run_dir, reference):
    digest = reference.get("sha256")
    if (not isinstance(digest, str) or len(digest) != len(hashlib.sha256().hexdigest()) or
            any(char not in "0123456789abcdef" for char in digest) or
            reference.get("file") != f"{SIDECAR_ROOT}/{digest}.json"):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
    path = _sidecar_path(run_dir, reference["file"])
    if not path.is_file():
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
    if state._fingerprint(payload) != digest:
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
    return payload


def policy_epoch(receipt, release, *, configured_steps, batch_size, settings, enrichment):
    root = Path(__file__).resolve().parents[1]
    owners = ("runtime/visits.py", "runtime/source_prefetch.py",
              "runtime/teacher_observation_capture.py", "learning/teacher_observations.py",
              "learning/learning_experiment.py", "learning/teacher_feedback.py",
              "learning/source_selection.py", "learning/lesson_guidance.py",
              "runtime/candidate_evidence.py", "runtime/state.py",
              "profiles/retention.py", "compatibility/historical_teacher_policy.py")
    return {
        "schema": EPOCH_SCHEMA,
        "implementation": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                           for name in owners},
        "teacher_source_sha256": receipt.get("teacher_source_sha256"),
        "factory_release_sha256": release.release_sha256,
        "semantic_graph_sha256": receipt.get("semantic_graph_sha256"),
        "source_manifest_sha256": receipt.get("source_manifest_sha256"),
        "feature_schema": "bilqis.teacher-student-region/v1",
        "selector": "existing-contextual-pick-or-inherited-bandit/v1",
        "option_rule": "ordinary-source-direct; autonomy-existing-selected-option",
        "fallback": "existing-engine-pick; unchanged-diagnostic-context-rules",
        "seed_derivation": "runtime.state._seed(run_id,generation,capability,step)",
        "configured_steps": configured_steps, "batch_size": batch_size,
        "retention_settings": asdict(settings) if settings is not None else None,
        "teaching_enrichment_enabled": enrichment,
        "cost_boundary": "host-monotonic-visit-entry-to-observation-finalization; includes capture and existing inference",
        "new_inference": False, "new_early_termination": False,
    }


def _topology_partition(receipt):
    from .model_topology import ModelTopologySpec, resolve_topology
    record = receipt.get("model_topology")
    if record is not None:
        return ModelTopologySpec.from_record(record).to_record()
    config = receipt.get("config", {})
    if {"layers", "heads", "width", "context"} <= set(config):
        return resolve_topology(config).to_record()
    return {"status": "NOT_MEASURED"}


class ObservationCapture:
    """Passive candidate-local recorder; owns no neural or teacher action."""

    def __init__(self, run_dir, receipt, *, enabled=True):
        self.run_dir, self.receipt, self.enabled = Path(run_dir), receipt, enabled
        self.started = time.monotonic() if enabled else None
        self.proposal = None
        self.steps = []

    def propose(self, release, school, capability, policy_key, policy, selection, *,
                configured_steps, effective_steps, batch_size, settings, enrichment,
                source_rows, teacher, parent_optimizer_step):
        if not self.enabled:
            return
        from ..learning.teacher_observations import student_region
        from ..factory.schedule import schedule_program_from_executable_release
        epoch = policy_epoch(self.receipt, release, configured_steps=configured_steps,
            batch_size=batch_size, settings=settings, enrichment=enrichment)
        epoch_ref = store_sidecar(self.run_dir, epoch)
        context = {"run_id": self.receipt["run_id"], "generation": self.receipt["generation"],
                   "visit": school.visits, "capability": capability, "phase": school.stage,
                   "durable_parent": self.receipt["school"]["current_student"],
                   "parent_optimizer_step": parent_optimizer_step}
        self.attempt_id = state._fingerprint({"schema": SCHEMA, **context})
        option = self.selected_option
        self.proposal = {
            "schema": PROPOSAL_SCHEMA, "attempt_id": self.attempt_id,
            "provenance": context, "capability": capability, "phase": school.stage,
            "frontier_context": {"active_grades": list(school.active_grades),
                                 "introduction_frontiers": list(school.introduction_frontiers),
                                 "carried_mastery_debt": list(school.carried_mastery_debt)},
            "offered_options": list(release.execution_plan.capability_map[capability].teaching_option_ids),
            "source_binding": asdict(release.source_bindings.by_capability[capability]),
            "selected_provider": {"id": release.execution_plan.capability_map[capability].provider_id,
                "implementation_sha256": release.execution_plan.capability_map[capability].provider_implementation_sha256},
            "selected_option": option, "policy_key": policy_key, "parameters": _plain(policy),
            "selection_route": {"option": self.selection_route, "policy": selection},
            "offered_policies": _plain(teacher.get("strategies", {})),
            "configured_steps": configured_steps, "effective_steps": effective_steps,
            "batch_size": batch_size, "policy_evidence_epoch": epoch_ref,
            "partition": {"model_topology": _topology_partition(self.receipt),
                          "initialization": self.receipt.get("model_initialization", {"status": "NOT_MEASURED"}),
                          "model_implementation": self.receipt.get("model_implementation"),
                          "factory_release_sha256": release.release_sha256},
            "student_region": student_region(self.receipt,
                schedule_program_from_executable_release(release), capability, school.stage, teacher,
                curriculum_scope=(str(self.receipt.get("curriculum_mode", "")) + "/" + str(self.receipt.get("numeric_maximum", ""))),
                numeric_maximum=self.receipt.get("numeric_maximum")),
            "selection_source_context": store_sidecar(self.run_dir, {"rows": source_rows}),
        }
        self.proposal_id = state._fingerprint(self.proposal)
        self.proposal_ref = store_sidecar(self.run_dir, self.proposal)

    def select_option(self, capability, selected):
        self.selected_option = selected or "source.direct/" + capability
        self.selection_route = "AUTONOMY_EXISTING_FIRST_RELEASED_OPTION" if selected else "ORDINARY_DIRECT"

    def delivery(self, release, capability, step, rows, *, option_rows, priority,
                 preservation, support, enrichment, guidance, controls, seed, prior=(), mentors=None):
        if not self.enabled:
            return
        source_ids = {row["id"] for row in option_rows}
        delivered = [row for row in rows if row["id"] in source_ids]
        description = (asdict(describe_delivered_teaching(
            release, capability, self.selected_option, delivered)) if delivered else None)
        roles = {"selected_option": source_ids, "weakness_replay": {row["id"] for row in priority},
                 "preservation": {row["id"] for row in preservation},
                 "retention_support": {row["id"] for row in support},
                 "enrichment": {row["id"] for row in enrichment},
                 "prior_rehearsal": {row["id"] for row in prior}}
        positioned = []
        for row in rows:
            kinds = [role for role, ids in roles.items() if row["id"] in ids]
            if not kinds:
                kinds = ["constructed_target"]
            owner = release.execution_plan.capability_map.get(row.get("capability"))
            positioned.append({"row": store_sidecar(self.run_dir, row), "roles": kinds,
                "provider_id": owner.provider_id if owner is not None else None,
                "provider_implementation_sha256": owner.provider_implementation_sha256 if owner is not None else None})
        payload = {"attempt_id": self.attempt_id, "proposal_id": self.proposal_id,
            "step": step, "seed": seed, "delivered_teaching": description,
            "positions": positioned, "guidance": _plain(guidance), "mentors": _plain(mentors),
            "controls": _plain(controls),
            "realization_changed": [row["id"] for row in rows] != [row["id"] for row in option_rows]}
        self.steps.append(store_sidecar(self.run_dir, payload))

    def finish(self, event, *, decision, paired, protected, stage, attempted, retained):
        if not self.enabled:
            return
        from ..learning.teacher_observations import (
            candidate_outcome, portable_v1_observation, MeasurementStatus, _score_pair,
        )
        outcome = candidate_outcome(decision, paired=paired, protected=protected, stage=stage,
            attempted_steps=attempted, retained_steps=retained,
            wall_seconds=max(0., time.monotonic() - self.started))
        skip_score = _score_pair((event.get("target_probe_correct"), event.get("target_probe_total")))
        if not attempted and skip_score is not None:
            outcome["target"]["before"] = {"status": MeasurementStatus.MEASURED, "value": event["target_probe_correct"]}
            outcome["target"]["total"] = {"status": MeasurementStatus.MEASURED, "value": event["target_probe_total"]}
        envelope = {"schema": SCHEMA, "attempt_id": self.attempt_id,
            "proposal_id": self.proposal_id, "proposal": self.proposal_ref,
            "steps": list(self.steps), "outcome": outcome,
            "portable_v1": portable_v1_observation(self.proposal["student_region"],
                {"family": "RELEASED_TEACHING_OPTION", "effective_policy_key": self.proposal["policy_key"],
                 "parameters": {**self.proposal["parameters"], "option_id": self.proposal["selected_option"],
                                "candidate_steps": self.proposal["effective_steps"], "batch_size": self.proposal["batch_size"]}}, outcome),
            "attempt_status": "SELECTION_SKIPPED" if not attempted else "CANDIDATE_ATTEMPTED",
            "publication_status": "PROVISIONAL_RAM_ACCEPTANCE" if retained else "NOT_RETAINED_IN_RAM",
            "selection_skip": {key: event[key] for key in ("reason", "target_probe_correct", "target_probe_total") if key in event}}
        event["teacher_observation"] = {"attempt_id": self.attempt_id,
            "proposal_id": self.proposal_id, "envelope": store_sidecar(self.run_dir, envelope)}


def read_observation(run_dir, event):
    reference = event["teacher_observation"]
    envelope = read_sidecar(run_dir, reference["envelope"])
    if (envelope.get("attempt_id") != reference["attempt_id"] or
            envelope.get("proposal_id") != reference["proposal_id"]):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)
    proposal = read_sidecar(run_dir, envelope["proposal"])
    if (state._fingerprint(proposal) != envelope["proposal_id"] or
            proposal.get("attempt_id") != envelope["attempt_id"]):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)
    for field in ("policy_evidence_epoch", "selection_source_context"):
        if field in proposal:
            read_sidecar(run_dir, proposal[field])
    steps = [read_sidecar(run_dir, step) for step in envelope["steps"]]
    for index, step in enumerate(steps, start=1):
        if (step.get("attempt_id") != envelope["attempt_id"] or
                step.get("proposal_id") != envelope["proposal_id"] or step.get("step") != index):
            ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)
        for position in step["positions"]:
            position["row"] = read_sidecar(run_dir, position["row"])
        selected = [position["row"] for position in step["positions"] if "selected_option" in position["roles"]]
        delivery = step.get("delivered_teaching")
        if selected and (not isinstance(delivery, dict) or
                delivery.get("specimen_content_sha256") != content_digest(selected) or
                delivery.get("specimen_ids") != list(dict.fromkeys(row["id"] for row in selected))):
            ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)
    return {**envelope, "proposal": proposal, "steps": steps,
            "publication": event.get("teacher_observation_publication", {"status": "NOT_PUBLISHED"}),
            "event_id": event.get("event_id")}
