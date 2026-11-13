"""Neural-inert generic next-grade admission readiness proof."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.curriculum import AnswerFamily, Capability, Course, Grade
from bilqis_mlx.curriculum_compiler import (
    CapabilityNode, CurriculumAST, FiniteTypedInput, TypedExpressionTemplate,
    compile_typed_candidate_package,
    compile_ast,
)
from bilqis_mlx.grade_transition import candidate_package_digest, cumulative_exam_digest
from bilqis_mlx.compatibility.grade_transition import next_grade_readiness
from bilqis_mlx.curriculum.scheduler import Assessment, Score, start_new
from bilqis_mlx.semantics.core import Operation, Signature
from bilqis_mlx.next_grade_review import QUESTION_IDS, SCHEMA, evidence_references, load_review, subject_digest
from bilqis_mlx.verification.review_evidence import EvidenceContext, verifier_digest


def _capability(grade, index, *, root):
    return Capability(f"{grade}.{index}", "fixture", f"repo:fixture/{grade}/{index}",
                      (root,), (root,), (), (),
                      (AnswerFamily("binary", ("FALSE", "TRUE")),),
                      "fixture.lesson", "fixture.oracle")


class _Backend:
    def __init__(self, identity):
        self.identity = identity

    def invoke(self, operation, values, world_contract):
        return not values[0]


class GradeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.pointer = Checkpoint("a" * 64, "fixture-complete", 42, True)
        a = Grade("A", tuple(_capability("A", i, root=f"fixture.a.{i}")
                              for i in range(6)), "a" * 64,
                  tuple((f"A.{i}", 2) for i in range(6)))
        b = Grade("B", tuple(_capability("B", i, root=f"fixture.b.{i}")
                              for i in range(6)), "b" * 64,
                  tuple((f"B.{i}", 2) for i in range(6)))
        self.previous = Course((a, b), "fixture/a-b", "1" * 64, "b" * 64)
        base = start_new(self.previous, self.pointer)
        self.state = replace(base, active_grades=("A", "B"), grade_index=1,
                             stage="AWAITING_NEXT_GRADE", queue=(),
                             champions={"A": self.pointer, "B": self.pointer},
                             latest_rubric_digest="b" * 64)
        c = Grade("C", tuple(_capability("C", i, root="fixture.negate")
                              for i in range(6)), "c" * 64,
                  tuple((f"C.{i}", 2) for i in range(6)))
        self.successor = Course((a, b, c), "fixture/a-b-c", "2" * 64, "c" * 64)
        scores = {cap.id: Score(2, 2) for grade in self.previous.grades
                  for cap in grade.capabilities}
        self.assessment = Assessment(self.pointer.sha256, self.pointer.optimizer_step,
                                     self.previous.digest(), "b" * 64, scores,
                                     "independent-fixture-exam")
        operation = Operation(700, "fixture.negate", Signature(("Boolean",), "Boolean"),
                              "d" * 64)
        nodes = tuple(CapabilityNode(cap.id, "C", cap.taught_roots, (), (),
                                     ("binary",), "fixture.oracle", cap.source_anchor)
                      for cap in c.capabilities)
        ast = CurriculumAST("fixture-semantic/v1", nodes)
        template = TypedExpressionTemplate(operation, (
            FiniteTypedInput("Boolean", (False, True)),))
        self.operations = {operation.symbol: operation}
        self.package = compile_typed_candidate_package(
            ast, operations=self.operations,
            templates={node.id: template for node in nodes},
            source=_Backend("source-fixture"), independent=_Backend("independent-fixture"),
            seed=9, specimens_per_split=2)

    def _review_context(self, directory, package):
        directory = Path(directory)
        artifact = directory / "source-witness.json"
        artifact.write_text('{"independent":"fixture"}')
        record = {
            "schema": SCHEMA, "authority": "IPR-0220/grade-questions-20261017",
            "grade": "C", "parent_release": self.previous.version,
            "semantic_release": "fixture-semantic/v1", "modality": "TEXT_ONLY",
            "selected": "semantic-binding",
            "candidates": [
                {"id": "semantic-binding", "source": "receipt:candidate",
                 "text_model_relevance": "DIRECT_TEXT_SEMANTIC_TRANSFER",
                 "needs_neural_learning": "fixture transfer evidence",
                 "smallest_increment": "one typed primitive",
                 "prerequisites": [{"id": "A.0", "state": "MASTERED",
                                    "evidence": "receipt:prerequisite"}],
                 "frontloaded_foundations": [],
                 "unlocks": [{"capability": "D.0", "via": "semantic-binding",
                              "why": "fixture downstream composition"}]},
                {"id": "codec", "source": "receipt:other",
                 "text_model_relevance": "DIRECT_TEXT_SEMANTIC_TRANSFER",
                 "needs_neural_learning": "alternative",
                 "smallest_increment": "alternative", "prerequisites": [],
                 "frontloaded_foundations": [], "unlocks": []}],
            "decision": {"why_now": "fixture", "why_not_alternatives": {"codec": "fixture"},
                         "what_changed_since_last_grade": "fixture",
                         "expected_near_term_transfer": "fixture",
                         "smallest_staircase_step": "fixture"},
            "semantic_function_families": {
                name: {"posture": "DEFERRED", "rationale": "not language yet"}
                for name in ("association", "disambiguation", "identification")},
            "reviews": {},
        }
        for phase in ("selection", "construction", "admission"):
            record["reviews"][phase] = {
                question: {"status": "EVIDENCED", "evidence": [f"receipt:{phase}:{question}"]}
                for question in QUESTION_IDS}
            record["reviews"][phase]["subject_sha256"] = subject_digest(record, phase)
        claims = {
            "receipt:candidate": ["candidate:semantic-binding:source"],
            "receipt:other": ["candidate:codec:source"],
            "receipt:prerequisite": ["prerequisite:A.0:MASTERED"],
            "receipt:cumulative": ["cumulative_exam:" + cumulative_exam_digest(self.assessment)],
            "receipt:release": [
                "release:fixture-semantic/v1:package:" + candidate_package_digest(package) +
                ":APPROVED_FOR_ADMISSION"] if package is not None else [],
        }
        if getattr(self, "stage_qualified", False):
            prerequisite = next(node for node in package.ast_nodes if node.id == "C.0")
            node_digest = hashlib.sha256(json.dumps(asdict(prerequisite), sort_keys=True,
                                                     separators=(",", ":")).encode()).hexdigest()
            claims["receipt:stages"] = ["stage_mastery:C.0:" + node_digest + ":" +
                self.pointer.sha256 + ":" + str(self.pointer.optimizer_step)]
        for phase in record["reviews"]:
            for question in QUESTION_IDS:
                claims[f"receipt:{phase}:{question}"] = [f"review:{phase}:{question}"]
        manifest = {"schema": "bilqis.review-evidence/v1", "grade": "C",
                    "verifier_sha256": verifier_digest(),
                    "parent_release": self.previous.version,
                    "semantic_release": "fixture-semantic/v1",
                    "subject_sha256": subject_digest(record), "receipts": [
                        {"id": identity, "claims": receipt_claims,
                         "qualification": "INDEPENDENTLY_QUALIFIED",
                         "producer": "fixture-source", "reviewer": "fixture-reviewer",
                         "artifacts": [{"path": artifact.name,
                                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                        "source": "fixture:source", "revision": "fixture/v1"}]}
                        for identity, receipt_claims in claims.items()]}
        manifest_path = directory / "evidence.json"
        manifest_path.write_text(json.dumps(manifest))
        context = EvidenceContext(manifest_path,
                                  hashlib.sha256(manifest_path.read_bytes()).hexdigest(), directory)
        inventory = context.inspect(grade="C", parent_release=self.previous.version,
                                    semantic_release="fixture-semantic/v1",
                                    subject_sha256=subject_digest(record))
        for phase in record["reviews"]:
            record["reviews"][phase]["evidence_sha256"] = inventory.digest_for(
                evidence_references(record, phase))
        (directory / "C.json").write_text(json.dumps(record))
        return context

    def _ready(self, **changes):
        values = dict(parent_release=self.previous.version, candidate_package=self.package,
                      candidate_semantic_release="fixture-semantic/v1",
                      semantic_release="fixture-semantic/v1",
                      approved_release_receipt="receipt:release",
                      source_operations=self.operations,
                      cumulative_exam_receipt="receipt:cumulative",
                      source_backend=_Backend("source-fixture"),
                      independent_backend=_Backend("independent-fixture"))
        values.update(changes)
        assessment = values.pop("assessment", self.assessment)
        with tempfile.TemporaryDirectory() as temp:
            context = self._review_context(temp, values["candidate_package"])
            values["review_evidence"] = context
            def local_review(grade, *, parent_release=None, phase="selection", evidence=None):
                return load_review(grade, directory=Path(temp), parent_release=parent_release,
                                   phase=phase, evidence=evidence)
            with patch("bilqis_mlx.next_grade_review.load_review", side_effect=local_review):
                result = next_grade_readiness(self.previous, self.successor, self.state,
                                              assessment, **values)
        return result

    def test_unfamiliar_source_candidate_is_ready_without_state_mutation(self):
        before = (self.previous, self.state, self.assessment)
        first = self._ready()
        second = self._ready()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "READY_FOR_HUMAN_ADMISSION_REVIEW")
        self.assertEqual(first["planned_grade"], "C")
        self.assertEqual(len(first["planned_capabilities"]), 6)
        self.assertEqual(first["planned_vocabulary_operations"], ["fixture.negate"])
        self.assertEqual(first["actual_neural_updates"], 0)
        self.assertFalse(first["training_authorized"])
        self.assertEqual(first["review_report"]["status"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertEqual(before, (self.previous, self.state, self.assessment))

    def test_missing_source_candidate_and_release_claim_block_only_future_grade(self):
        result = self._ready(candidate_package=None, approved_release_receipt=None)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("GRADE_ADMISSION_SOURCE_CANDIDATE_MISSING", result["blockers"])
        self.assertIn("GRADE_ADMISSION_EXTERNAL_RELEASE_APPROVAL_MISSING", result["blockers"])
        self.assertEqual(self.state.grade, "B")
        self.assertEqual(self.previous.version, "fixture/a-b")

    def test_stale_parent_partial_and_mixed_checkpoint_are_blocked(self):
        stale = self._ready(parent_release="wrong-parent")
        self.assertIn("GRADE_ADMISSION_PARENT_RELEASE_MISMATCH", stale["blockers"])
        partial_scores = dict(self.assessment.scores)
        partial_scores["A.0"] = Score(1, 2)
        partial = self._ready(assessment=replace(self.assessment, scores=partial_scores))
        self.assertTrue(any("COMPLETE_PERFECT" in blocker for blocker in partial["blockers"]))
        mixed = self._ready(assessment=replace(self.assessment, optimizer_step=43))
        self.assertTrue(any("ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE" in blocker
                            for blocker in mixed["blockers"]))

    def test_tampered_gold_and_incomplete_finite_coverage_are_blocked(self):
        item = self.package.tests[0]
        forged = replace(self.package, tests=(replace(
            item, proof=replace(item.proof, result=not item.proof.result)), *self.package.tests[1:]))
        self.assertIn("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID", self._ready(
            candidate_package=forged)["blockers"])
        truncated = replace(self.package, tests=self.package.tests[::2])
        self.assertIn("GRADE_ADMISSION_CANDIDATE_COVERAGE_INVALID", self._ready(
            candidate_package=truncated)["blockers"])

    def test_unrelated_constructions_cannot_borrow_a_canonical_ast(self):
        unrelated = Operation(999, "fixture.unrelated", Signature(("Boolean",), "Boolean"), "e" * 64)
        ast = CurriculumAST(self.package.ast_version, tuple(
            replace(node, roots=(unrelated.symbol,)) for node in self.package.ast_nodes))
        template = TypedExpressionTemplate(unrelated, (FiniteTypedInput("Boolean", (False, True)),))
        forged = compile_typed_candidate_package(
            ast, operations={unrelated.symbol: unrelated},
            templates={node.id: template for node in ast.nodes},
            source=_Backend("source-fixture"), independent=_Backend("independent-fixture"))
        forged = replace(forged, ast_nodes=self.package.ast_nodes, ast_sha256=self.package.ast_sha256)
        result = self._ready(candidate_package=forged,
                             source_operations={**self.operations, unrelated.symbol: unrelated})
        self.assertIn("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID", result["blockers"])

    def test_unsupported_declared_answer_family_cannot_pass_with_binary_specimens(self):
        grade = self.successor.grades[-1]
        changed = replace(grade, capabilities=tuple(replace(cap, answer_families=(
            *cap.answer_families, AnswerFamily("integer_0_3", ("0", "1", "2", "3"))))
            for cap in grade.capabilities))
        self.successor = replace(self.successor, grades=(*self.successor.grades[:-1], changed))
        ast = CurriculumAST(self.package.ast_version, tuple(replace(
            node, answers=("binary", "integer_0_3")) for node in self.package.ast_nodes))
        forged = replace(self.package, ast_nodes=ast.nodes, ast_sha256=ast.digest())
        self.assertIn("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID", self._ready(
            candidate_package=forged)["blockers"])

    def test_package_ast_digest_and_stage_cannot_be_forged(self):
        tampered = replace(self.package, ast_sha256="0" * 64)
        self.assertIn("GRADE_ADMISSION_CANDIDATE_AST_DRIFT", self._ready(
            candidate_package=tampered)["blockers"])
        staged = replace(self.package, ast_nodes=tuple(
            replace(node, stage=9) for node in self.package.ast_nodes))
        self.assertIn("GRADE_ADMISSION_CANDIDATE_BINDINGS_MISMATCH", self._ready(
            candidate_package=staged)["blockers"])

    def test_unattested_cumulative_scores_and_missing_oracles_fail_closed(self):
        self.assertIn("GRADE_ADMISSION_CUMULATIVE_ATTESTATION_MISSING", self._ready(
            cumulative_exam_receipt=None)["blockers"])
        self.assertIn("GRADE_ADMISSION_INDEPENDENT_BACKENDS_MISSING", self._ready(
            independent_backend=None)["blockers"])

    def test_generic_target_retains_prior_grade_dependencies_without_regenerating_them(self):
        grade = self.successor.grades[-1]
        changed = replace(grade, capabilities=tuple(
            replace(cap, prerequisites=("A.0",)) for cap in grade.capabilities))
        self.successor = replace(self.successor, grades=(*self.successor.grades[:-1], changed))
        ast = replace(compile_ast(self.successor), version="fixture-semantic/v1")
        template = dict(self.package.construction_templates)["C.0"]
        targets = tuple(cap.id for cap in changed.capabilities)
        package = compile_typed_candidate_package(
            ast, operations=self.operations, templates={identity: template for identity in targets},
            source=_Backend("source-fixture"), independent=_Backend("independent-fixture"),
            target_capabilities=targets, qualified_prerequisites=("A.0",), specimens_per_split=2)
        result = self._ready(candidate_package=package)
        self.assertEqual(result["status"], "READY_FOR_HUMAN_ADMISSION_REVIEW")
        self.assertEqual({row.capability for row in package.lessons}, set(targets))
        self.assertEqual(len(package.ast_nodes), 18)

    def test_new_stage_must_demonstrate_mastery_before_dependent_admission(self):
        grade = self.successor.grades[-1]
        changed = replace(grade, capabilities=(grade.capabilities[0], *(
            replace(cap, prerequisites=("C.0",)) for cap in grade.capabilities[1:])),
            teaching_stages=(("C.0",), tuple(cap.id for cap in grade.capabilities[1:])))
        self.successor = replace(self.successor, grades=(*self.successor.grades[:-1], changed))
        ast = replace(compile_ast(self.successor), version="fixture-semantic/v1")
        targets = tuple(cap.id for cap in changed.capabilities)
        template = dict(self.package.construction_templates)["C.0"]
        package = compile_typed_candidate_package(
            ast, operations=self.operations, templates={identity: template for identity in targets},
            source=_Backend("source-fixture"), independent=_Backend("independent-fixture"),
            target_capabilities=targets, qualified_prerequisites=("C.0",), specimens_per_split=2)
        self.assertIn("GRADE_ADMISSION_EARLIER_STAGE_MASTERY_REQUIRED:C.0", self._ready(
            candidate_package=package)["blockers"])
        self.assertIn("GRADE_ADMISSION_EARLIER_STAGE_MASTERY_REQUIRED:C.0", self._ready(
            candidate_package=package, stage_mastery_receipts={"C.0": "receipt:stages"})["blockers"])
        self.stage_qualified = True
        qualified = self._ready(candidate_package=package, stage_mastery_receipts={"C.0": "receipt:stages"})
        self.assertEqual(qualified["status"], "READY_FOR_HUMAN_ADMISSION_REVIEW")


if __name__ == "__main__":
    unittest.main()
