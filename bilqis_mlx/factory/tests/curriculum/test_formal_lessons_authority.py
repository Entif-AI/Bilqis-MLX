"""Authority and integration tests for task-scoped formal lessons."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.formal_lessons import (
    FORMAL_LESSON_STATUS, LEARNING_UNVERIFIED,
    check_formal_lesson, construct_formal_lesson,
)
from bilqis_mlx.semantics.atlas_projection import (
    FormalDomainBinding, compile_atlas_release, persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import TypedValue

from bilqis_mlx.factory.tests.formal_lesson_fixtures import (
    FORMAL, RELEASE, _case, _selection, _source,
)


class FormalLessonAuthorityTests(unittest.TestCase):
    def test_real_a01_release_with_a13_grants_if_supplied(self):
        corpus = os.environ.get("BILQIS_ATLAS_REAL_CORPUS")
        if not corpus:
            self.skipTest("real pinned A01 corpus not supplied")
        root = Path(__file__).resolve().parents[3]
        prior = root / "bilqis_mlx/semantics/copular_registry_v1.json"
        boolean = root / "bilqis_mlx/semantics/legacy_abi_v1.json"
        numeric = root / "bilqis_mlx/semantics/numeric_v1.json"
        bindings = (
            FormalDomainBinding(
                "boolean", "bilqis_mlx/semantics/legacy_abi_v1.json",
                hashlib.sha256(boolean.read_bytes()).hexdigest(),
                ("legacy:cogal.operator.NOT", "legacy:cogal.operator.AND"),
                ("B.NOT", "B.AND")),
            FormalDomainBinding(
                "numeric", "bilqis_mlx/semantics/numeric_v1.json",
                hashlib.sha256(numeric.read_bytes()).hexdigest(),
                ("bilqis.numeric/v1:school.op.COUNT",
                 "bilqis.numeric/v1:school.op.SUCC"),
                ("C.COUNT", "C.SUCCESSOR")))
        release = compile_atlas_release(
            corpus, Path(corpus) / "coverage.json", prior, bindings)
        with tempfile.TemporaryDirectory() as directory:
            artifact = persist_atlas_release(release, directory)
            selection = AtlasArtifactSelection(
                artifact.path, artifact.bundle_id, release.digest,
                release.source_bundle_id)
            for semantic_id, operator_id, operands, expected in (
                    (FORMAL[0][0], "BOOL_NOT", (("Boolean", True),), False),
                    (FORMAL[1][0], "BOOL_AND",
                     (("Boolean", True), ("Boolean", False)), False),
                    (FORMAL[2][0], "COUNT",
                     (("EntitySet", ("alpha", "beta")),), 2),
                    (FORMAL[3][0], "SUCC", (("Number", 2),), 3)):
                with self.subTest(operator=operator_id):
                    binding, typed = _case(
                        operator_id, *operands, release=release.digest)
                    lesson = construct_formal_lesson(
                        selection, semantic_id, typed, binding)
                    self.assertEqual(lesson.positive.value, expected)
                    self.assertTrue(check_formal_lesson(
                        lesson, lesson.positive, selection, binding))
                    self.assertFalse(check_formal_lesson(
                        lesson, lesson.contrast, selection, binding))

    def test_four_released_laws_have_typed_source_contrasts(self):
        cases = (
            (FORMAL[0][0], "BOOL_NOT", (("Boolean", True),), False),
            (FORMAL[1][0], "BOOL_AND",
             (("Boolean", True), ("Boolean", False)), False),
            (FORMAL[2][0], "COUNT",
             (("EntitySet", ("alpha", "beta")),), 2),
            (FORMAL[3][0], "SUCC", (("Number", 2),), 3),
        )
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            for semantic_id, operator_id, operands, expected in cases:
                with self.subTest(operator=operator_id):
                    binding, typed = _case(operator_id, *operands)
                    lesson = construct_formal_lesson(
                        _selection(), semantic_id, typed, binding)
                    self.assertEqual(lesson.positive.value, expected)
                    self.assertNotEqual(
                        lesson.positive.value, lesson.contrast.value)
                    self.assertEqual(
                        lesson.prerequisite_closure, lesson.constituents)
                    self.assertEqual(
                        lesson.variation_axes, ("typed-answer-contrast",))
                    self.assertEqual(lesson.status, FORMAL_LESSON_STATUS)
                    self.assertEqual(
                        lesson.learning_state, LEARNING_UNVERIFIED)
                    self.assertTrue(check_formal_lesson(
                        lesson, lesson.positive, _selection(), binding))
                    self.assertFalse(check_formal_lesson(
                        lesson, lesson.contrast, _selection(), binding))

    def test_checker_rejects_forged_gold_without_calling_generator(self):
        binding, inputs = _case("SUCC", ("Number", 2))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            lesson = construct_formal_lesson(
                _selection(), FORMAL[3][0], inputs, binding)
            with patch(
                    "bilqis_mlx.factory.formal_lessons.construct_formal_lesson",
                    side_effect=AssertionError("checker called generator")):
                self.assertTrue(check_formal_lesson(
                    lesson, lesson.positive, _selection(), binding))
            forged = replace(
                lesson, positive=TypedValue("Number", 4, RELEASE))
            with self.assertRaises(BilqisError) as caught:
                check_formal_lesson(
                    forged, forged.positive, _selection(), binding)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_FORMAL_LESSON_SOURCE_EVIDENCE_MISMATCH")

    def test_revoked_rights_wrong_arity_and_wrong_type_fail_closed(self):
        binding, inputs = _case("SUCC", ("Number", 2))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            lesson = construct_formal_lesson(
                _selection(), FORMAL[3][0], inputs, binding)
            grants = tuple(
                replace(grant, revoked=True)
                if grant.source_handle == inputs[0].source_handle else grant
                for grant in binding.frontier.grants)
            revoked = replace(
                binding, frontier=replace(binding.frontier, grants=grants))
            with self.assertRaises(BilqisError):
                check_formal_lesson(
                    lesson, lesson.positive, _selection(), revoked)
            for changed in (
                    replace(
                        binding, frontier=replace(
                            binding.frontier, rights_epoch=2)),
                    replace(
                        binding, frontier=replace(
                            binding.frontier, correction_generation=2)),
                    replace(
                        binding, task=replace(
                            binding.task, purpose="SERVING")),
                    replace(
                        binding, task=replace(
                            binding.task, semantic_release="f" * 64))):
                with self.subTest(changed=changed.task):
                    with self.assertRaises(BilqisError):
                        check_formal_lesson(
                            lesson, lesson.positive, _selection(), changed)
            with self.assertRaises(BilqisError):
                construct_formal_lesson(
                    _selection(), FORMAL[3][0], (), binding)
            wrong = (TypedValue(
                "Boolean", True, RELEASE, source_handle=inputs[0].source_handle),)
            with self.assertRaises(BilqisError):
                construct_formal_lesson(
                    _selection(), FORMAL[3][0], wrong, binding)
            boolean_binding, boolean_inputs = _case(
                "BOOL_NOT", ("Boolean", True))
            with self.assertRaises(BilqisError):
                construct_formal_lesson(
                    _selection(), FORMAL[3][0],
                    boolean_inputs, boolean_binding)


if __name__ == '__main__':
    unittest.main()
