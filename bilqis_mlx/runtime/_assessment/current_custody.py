"""Current/historical assessment source dispatch and cohort custody."""
from __future__ import annotations

import json

from ...errors import ErrorBus, FACTORY
from ...factory.executable_release import ExecutableAdmissionReceipt
from ...factory.generation import draw_executable_release_rows
from ...generated_assessment import EXECUTABLE_COHORT_SCHEMA, verify_stored_cohort
from ...live_curriculum import cohort_contract as _cohort_contract
from ..source_execution import SourceExecutionContext
from ..state import _durable_json
from .executable_custody import _load_executable_cohort

_CURRENT_ADMISSION_DRIFT = "FACTORY_EXECUTABLE_SAVED_COHORT_CURRENT_ADMISSION_DRIFT"

def _draw_live_rows(source_root, graph, *, seed, capability=None, each=None,
                    course=None, executable_release=None,
                    source_context: SourceExecutionContext | None = None):
    """Draw from bound v2 authority, retaining the historical Course entrypoint."""
    if source_context is not None:
        if not isinstance(source_context, SourceExecutionContext):
            raise TypeError(FACTORY.EXECUTION.ASSESSMENT_SOURCE_CONTEXT_REQUIRED.legacy_codes[0])
        return source_context.draw_rows(seed=seed, capability=capability, each=each)
    if executable_release is not None:
        from ...source_adapters.school import live_source_registry
        return draw_executable_release_rows(
            source_root, graph, executable_release, live_source_registry(),
            seed=seed, capability=capability, each=each)
    if course is None:
        raise ValueError("FACTORY_RELEASE_REQUIRED_FOR_SOURCE_GENERATION")
    from .. import assessment as _assessment
    return _assessment.draw_course_rows(
        source_root, graph, course, seed=seed, capability=capability, each=each)


def released_lesson_source_identity(release, capability: str) -> tuple[str, str]:
    """Give teaching telemetry its actual admitted v2 provider provenance."""
    execution = release.execution_plan.capability_map.get(capability)
    binding = release.source_bindings.by_capability.get(capability)
    if execution is None or binding is None:
        raise ValueError("FACTORY_LESSON_CAPABILITY_NOT_ADMITTED")
    descriptor = next((item for item in release.source_adapters
                       if item.adapter_id == execution.provider_id), None)
    if (descriptor is None or descriptor.generator_id != binding.generator_id or
            binding.oracle_id not in descriptor.accepted_oracle_ids):
        raise ValueError("FACTORY_LESSON_PROVIDER_BINDING_DRIFT")
    return descriptor.cohort_generator, descriptor.implementation_sha256


def _persist_live_cohort(run_dir, manifest, course, cohort):
    """Make generation retry safe if a crash follows cohort publication."""
    rubric, release, generator, code_sha = _cohort_contract(course)
    if cohort.generator_version != generator or cohort.rubric_version != release:
        raise ValueError("HUMAN_TRAINER_COHORT_VERSION_MISMATCH")
    path = run_dir / "cohorts" / (cohort.digest + ".json")
    payload = {"schema": release,
               "source_manifest_sha256": manifest["manifest_sha256"],
               "rubric_sha256": rubric,
               "generator_version": generator,
               "generator_code_sha256": code_sha,
               "seed": cohort.seed,
               "cohort_sha256": cohort.digest, "rows": list(cohort.rows)}
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text()) != payload:
            raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_CUSTODY_DRIFT")
    else:
        _durable_json(path, payload)
    if json.loads(path.read_text()) != payload:
        raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_WRITEBACK_DRIFT")
    return str(path.relative_to(run_dir))


def _current_cohort_metadata_drift(*, cause: ValueError | None = None) -> None:
    """Raise the current reader's public metadata-drift wire error."""
    error = ValueError("HUMAN_TRAINER_COHORT_POINTER_METADATA_DRIFT")
    if cause is None:
        raise error
    raise error from cause


def _load_current_cohort(run_dir, manifest, course, pointer):
    """Read back one current-release cohort without changing its qualification state."""
    if not isinstance(pointer, dict):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_INVALID")
    sha = pointer.get("cohort_sha256")
    path_ref = pointer.get("cohort_file")
    if (not isinstance(sha, str) or len(sha) != 64 or
            path_ref != "cohorts/" + sha + ".json"):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_DRIFT")
    path = run_dir / path_ref
    if path.is_symlink() or not path.is_file():
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_MISSING")
    stored = json.loads(path.read_text())
    rubric, release, generator, code_sha = _cohort_contract(course)
    if (stored.get("schema") != release or
            stored.get("source_manifest_sha256") != manifest["manifest_sha256"] or
            stored.get("rubric_sha256") != rubric or
            stored.get("generator_version") != generator or
            stored.get("generator_code_sha256") != code_sha or
            stored.get("cohort_sha256") != sha or
            stored.get("seed") != pointer.get("cohort_seed")):
        _current_cohort_metadata_drift()
    try:
        return verify_stored_cohort(
            stored, sha, expected_rubric_sha256=rubric)
    except ValueError as exc:
        if str(exc) == "STORED_COHORT_CONTENT_DRIFT":
            raise ValueError(
                "HUMAN_TRAINER_COHORT_POINTER_CONTENT_DRIFT") from exc
        _current_cohort_metadata_drift(cause=exc)


def load_championship_cohort(run_dir, witness):
    """Verify an immutable earning cohort against its own admitted source identity."""
    sha = witness.get("cohort_sha256")
    if (not isinstance(sha, str) or len(sha) != 64 or
            any(char not in "0123456789abcdef" for char in sha)):
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_IDENTITY_REQUIRED")
    path = run_dir / "cohorts" / (sha + ".json")
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_MISSING")
    stored = json.loads(path.read_text())
    source_rubric = witness.get(
        "cohort_rubric_sha256", witness["rubric_sha256"])
    if (stored.get("cohort_sha256") != sha or
            stored.get("rubric_sha256") != source_rubric or
            stored.get("source_manifest_sha256") != witness["source_oracle_sha256"]):
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_SOURCE_DRIFT")
    try:
        cohort = verify_stored_cohort(
            stored, sha,
            expected_rubric_sha256=(source_rubric if stored.get("schema") ==
                                    EXECUTABLE_COHORT_SCHEMA else None))
    except ValueError as exc:
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_CONTENT_DRIFT") from exc
    return cohort


def _verify_saved_cohort(run_dir, receipt, course, *, sealed_v1_release=None):
    exam = receipt.get("last_exam") or {}
    if exam.get("cohort_sha256") is None:
        return None
    if (receipt.get("factory_admission_v2") is not None and
            exam.get("factory_release_sha256") is not None):
        from ..admission import _read_executable_factory_release_artifact
        current = _read_executable_factory_release_artifact(run_dir, receipt)
        release = current
        if exam["factory_release_sha256"] != current.release_sha256:
            if exam.get("schema") != EXECUTABLE_COHORT_SCHEMA:
                raise ValueError(
                    "FACTORY_EXECUTABLE_SAVED_COHORT_PREDECESSOR_POINTER_INVALID")
            predecessor_sha = exam["factory_release_sha256"]
            if current.predecessor_release_sha256 != predecessor_sha:
                raise ValueError(
                    "FACTORY_EXECUTABLE_SAVED_COHORT_PREDECESSOR_UNAUTHORIZED")
            predecessor = _read_executable_factory_release_artifact(
                run_dir, {
                    "factory_release_sha256": predecessor_sha,
                    "factory_release_file":
                        f"factory-releases/{predecessor_sha}.json",
                })
            try:
                current.verify_successor_of(predecessor)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "FACTORY_EXECUTABLE_SAVED_COHORT_PREDECESSOR_LINEAGE_DRIFT"
                ) from exc

            raw_admission = receipt.get("factory_admission_v2")
            try:
                admission = ExecutableAdmissionReceipt(**raw_admission)
                admission.verify(current)
            except (TypeError, ValueError) as exc:
                raise ValueError(_CURRENT_ADMISSION_DRIFT) from exc
            student = (receipt.get("school") or {}).get("current_student") or {}
            student_step = student.get("optimizer_step")
            if (admission.semantic_graph_sha256 !=
                    receipt.get("semantic_graph_sha256") or
                    type(student_step) is not int or student_step < 0 or
                    admission.optimizer_step > student_step or
                    (admission.optimizer_step == student_step and
                     admission.student_sha256 != student.get("sha256"))):
                raise ValueError(_CURRENT_ADMISSION_DRIFT)
            if (exam.get("student_sha256") != admission.student_sha256 or
                    exam.get("optimizer_step") != admission.optimizer_step):
                raise ValueError(
                    "FACTORY_EXECUTABLE_SAVED_COHORT_PREDECESSOR_STUDENT_DRIFT")
            release = predecessor
        capabilities = tuple(exam.get("capabilities", ()))
        if not capabilities:
            raise ValueError("FACTORY_EXECUTABLE_SAVED_COHORT_SCOPE_REQUIRED")
        pointer = {
            key: exam[key] for key in (
                "factory_release_sha256", "capabilities", "rubric_sha256",
                "source_sha256", "cohort_sha256", "cohort_file",
                "cohort_seed")
            if key in exam
        }
        return _load_executable_cohort(
            run_dir,
            {"manifest_sha256": receipt["source_manifest_sha256"]},
            release, capabilities, pointer)
    from ..compatibility.assessment import verify_legacy_saved_cohort
    if sealed_v1_release is None:
        from ..admission import _verified_historical_cohort_release
        sealed_v1_release = _verified_historical_cohort_release(run_dir, receipt)
    return verify_legacy_saved_cohort(
        run_dir, receipt, course, sealed_v1_release=sealed_v1_release)
