"""Fail-closed architecture checks for SPEC-0001 curriculum-factory invariants.

This checker is intentionally structural. It does not prove pedagogy. It makes
the previously common escape hatches mechanically expensive: future grade
runtime forks, grade-letter dispatch inside generic factory code, and live
training/admission paths that fail to bind a FactoryRelease.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re

if __package__:
    from .quality import check_factory_closure as closure
else:
    from quality import check_factory_closure as closure


REPO_ROOT = Path(__file__).resolve().parents[1]
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
if __package__:
    from .quality.factory_architecture_rules import (
        FUTURE_GRADE_FILE, GENERIC_RUNTIME, _source, _function_calls,
        _grade_literal_dispatch, _legacy_course_usage, _import_from_module,
        _imports_trainer_facade, _compatibility_writer_calls,
    )
else:
    from quality.factory_architecture_rules import (
        FUTURE_GRADE_FILE, GENERIC_RUNTIME, _source, _function_calls,
        _grade_literal_dispatch, _legacy_course_usage, _import_from_module,
        _imports_trainer_facade, _compatibility_writer_calls,
    )


def _semantic_neutrality(root: Path) -> tuple[str, ...]:
    problems = []
    registrations = {"bilqis_mlx/factory/adapters.py",
                     "bilqis_mlx/factory/candidate_realizations.py"}
    for path in closure._generic_files(root):
        relative = path.relative_to(root)
        if relative.as_posix() in registrations:
            continue
        tree = ast.parse(_source(path), filename=str(path))
        release_aliases = closure._release_aliases(tree)
        for node in ast.walk(tree):
            targets = ()
            if isinstance(node, ast.Import):
                targets = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = _import_from_module(node, path, root / "bilqis_mlx")
                targets = (module, *(f"{module}.{alias.name}" for alias in node.names))
            for target in targets:
                if closure.CONCRETE_PROVIDER.search(target):
                    problems.append(f"{relative}:{node.lineno} "
                                    f"GENERIC_IMPORTS_CONCRETE_PROVIDER:{target}")
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    and node.id in release_aliases):
                problems.append(f"{relative}:{node.lineno} "
                                f"GENERIC_RELEASE_IDENTITY_REFERENCE:{node.id}")
            if isinstance(node, (ast.If, ast.IfExp, ast.While)):
                decision = node.test
            elif isinstance(node, ast.Match):
                decision = ast.Tuple(elts=[case.pattern for case in node.cases])
            else:
                continue
            identities = sorted(value for value in closure._strings(decision)
                                if closure.CAPABILITY_ID.fullmatch(value))
            if identities:
                problems.append(f"{relative}:{node.lineno} "
                                f"GENERIC_CAPABILITY_IDENTITY_DISPATCH:{','.join(identities)}")
    return tuple(problems)


def inspect_factory_architecture(root: Path) -> tuple[str, ...]:
    src = root / "bilqis_mlx"
    problems: list[str] = []
    if not (src / "factory").is_dir():
        return ("FACTORY_PACKAGE_MISSING",)

    problems.extend(_inspect_runtime_ownership(src, root))

    for relative in GENERIC_RUNTIME:
        path = root / relative
        paths = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for candidate in paths:
            if "tests" in candidate.relative_to(src).parts or not candidate.is_file():
                continue
            problems.extend(_grade_literal_dispatch(candidate, root))
            problems.extend(_legacy_course_usage(candidate, root))

    trainer = src / "trainer.py"
    operate_calls = _function_calls(trainer, "operate")
    if not operate_calls & {
            "_require_executable_factory_admission",
            "_ensure_executable_release"}:
        problems.append("bilqis_mlx/trainer.py OPERATE_BYPASSES_FACTORY_RELEASE")
    b_calls = _function_calls(trainer, "_adopt_executable_profile")
    if not b_calls & {
            "_require_executable_factory_admission",
            "_executable_factory_admission"}:
        problems.append("bilqis_mlx/trainer.py B_ADMISSION_BYPASSES_FACTORY_RELEASE")

    legacy = src / "grade_a_trainer.py"
    if legacy.is_file():
        tree = ast.parse(_source(legacy), filename=str(legacy))
        if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
               for node in tree.body):
            problems.append("bilqis_mlx/grade_a_trainer.py LEGACY_RUNTIME_OWNS_BEHAVIOR")

    transition = src / "grade_transition.py"
    if not transition.is_file():
        transition = src / "_release_views/grade_transition.py"
    if transition.is_file():
        tree = ast.parse(_source(transition))
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                    node.name in {"activate_numeric_grade", "next_grade_readiness"}):
                problems.append("bilqis_mlx/grade_transition.py RETIRED_CURRENT_TRANSITION")
            if isinstance(node, ast.ImportFrom) and any(
                    item.name in {"activate_numeric_grade", "next_grade_readiness"}
                    for item in node.names):
                problems.append("bilqis_mlx/grade_transition.py RETIRED_CURRENT_TRANSITION")
    staircase = src / "numeric_staircase.py"
    if not staircase.is_file():
        staircase = src / "_numeric_sources/numeric_staircase.py"
    if "_factory_admission" not in _function_calls(staircase, "_rebind"):
        problems.append("bilqis_mlx/numeric_staircase.py SCOPE_RELEASE_BYPASSES_FACTORY_RELEASE")

    problems.extend(_research_imports(src, root))
    problems.extend(_semantic_neutrality(root))
    problems.extend(_developmental_evidence_policy(root))
    return tuple(problems)


def _developmental_evidence_policy(root: Path) -> tuple[str, ...]:
    problems = []
    path = root / DEVELOPMENTAL_POLICY
    if not path.is_file():
        return ("DEVELOPMENTAL_EVIDENCE_POLICY_MISSING",)
    try:
        policy = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return ("DEVELOPMENTAL_EVIDENCE_POLICY_INVALID",)

    expected = {
        ("schema",): "bilqis.developmental-evidence-policy/v1",
        ("current_stage",): "FOUNDATION_ACQUISITION",
        ("generalization_status",): "MEASURE_ONLY",
        ("fixed_generalization_gate_authority",): "EXPLICIT_HUMAN_ADMISSION",
        ("current_acceptance", "teacher_forced_gold_allowed"): True,
        ("current_acceptance", "same_specimen_replay_allowed"): True,
        ("current_acceptance", "exact_memorization_counts_as_learning"): True,
        ("current_acceptance", "cache_memoization_retrieval_counts_as_learning"): True,
        ("current_acceptance", "held_out_required"): False,
        ("current_acceptance", "independent_source_family_required"): False,
        ("current_acceptance", "fresh_episode_required"): False,
        ("current_acceptance", "novel_composition_required"): False,
        ("current_acceptance", "allowed_evidence_kinds"): [
            "TEACHER_FORCED_ACQUISITION",
            "EXACT_TAUGHT_RECALL",
            "TAUGHT_COMPOSITION_REPLICATION",
        ],
        ("alpha_advancement", "basis"): "CURRENT_EARNED_COMPLEXITY_SUCCESS_RATIO",
        ("alpha_advancement", "previously_shown_examples_count"): True,
        ("alpha_advancement", "held_out_required"): False,
        ("alpha_advancement", "novelty_required"): False,
        ("alpha_advancement", "pool_growth"): "INCREMENTAL_OR_LOGARITHMIC",
        ("alpha_advancement", "complexity_growth"): "EARNED",
        ("candidate_retention", "immediate_target_gain_required"): False,
        ("candidate_retention", "protected_regression_checks_required"): True,
        ("candidate_retention", "no_gain_strategy_retirement_remains_teacher_owned"): True,
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
    for keys, value in expected.items():
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


def _research_imports(src, root):
    problems = []
    # Research/prototype packages cannot become dependencies of the canonical
    # released runtime. Keep this generic even before such a package exists.
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src)
        if set(relative.parts) & {"research", "compatibility", "tests"}:
            continue
        tree = ast.parse(_source(path), filename=str(path))
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom):
                module = ("bilqis_mlx", *relative.with_suffix("").parts)
                target = ".".join((*module[:-node.level], *(node.module or "").split("."))) if node.level else node.module or ""
            elif isinstance(node, ast.Import):
                for item in node.names:
                    if item.name.startswith("bilqis_mlx.research"):
                        problems.append(
                            f"{path.relative_to(root)}:{node.lineno} RUNTIME_IMPORTS_RESEARCH")
                continue
            if target is not None and (
                    target.startswith("bilqis_mlx.research") or
                    target.startswith(".research")):
                problems.append(
                    f"{path.relative_to(root)}:{node.lineno} RUNTIME_IMPORTS_RESEARCH")
    return problems


def _inspect_runtime_ownership(src, root):
    problems = []
    """Inspect compatibility writers and runtime ownership across production modules."""
    # A/B/C remain compatibility/provider modules during migration. There is no
    # permission to repeat the pattern for D or any later grade.
    for path in sorted(src.rglob("*.py")):
        if "tests" in path.relative_to(src).parts:
            continue
        tree = ast.parse(_source(path))
        if path.relative_to(src).parts[0] == "compatibility":
            problems.extend(_compatibility_writer_calls(tree, path, src))
        if path not in {src / "trainer.py", src / "cli.py"}:
            for node in ast.walk(tree):
                if _imports_trainer_facade(node, path, src):
                    problems.append(f"{path.relative_to(root)} LEAF_IMPORTS_TRAINER")
        if set(path.relative_to(src).parts) & {"compatibility", "research"}:
            continue
        match = FUTURE_GRADE_FILE.match(path.name)
        if match:
            problems.append(
                f"{path.relative_to(root)} FUTURE_GRADE_RUNTIME_FORK:{match.group(1).upper()}")

    return problems


if __name__ == "__main__":
    issues = inspect_factory_architecture(REPO_ROOT)
    for issue in issues:
        print(issue)
    if issues:
        raise SystemExit(1)
    print("FACTORY_ARCHITECTURE_OK")
