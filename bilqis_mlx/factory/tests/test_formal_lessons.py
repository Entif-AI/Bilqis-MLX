"""Task-scoped formal lessons: A01 identity, A07 semantics, A13 rights."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.formal_constructive import _resolve_from_bindings
from bilqis_mlx.factory.formal_lessons import (
    FORMAL_LESSON_STATUS, LEARNING_UNVERIFIED,
    check_formal_lesson, construct_formal_lesson,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, FormalDomainBinding, compile_atlas_release, persist_atlas_release,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, SourceKind, SourceOperand, TypedValue, default_registry,
    numeric_domain_digest, operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.core import literal
from bilqis_mlx.semantics.domains import FiniteDomain, SourceBinding, ValueCodec
from bilqis_mlx.semantics.laws import SourceLocator


RELEASE = "a" * 64
BUNDLE = "b" * 64
SOURCE = "c" * 64
PRINCIPAL = "synthetic:person"
TENANT = "synthetic:tenant"
PURPOSE = "TRAINING"
JURISDICTION = "synthetic:region"
SCOPE = "synthetic:task"
FORMAL = (
    ("legacy:cogal.operator.NOT", "boolean", "BOOL_NOT"),
    ("legacy:cogal.operator.AND", "boolean", "BOOL_AND"),
    ("bilqis.numeric/v1:school.op.COUNT", "numeric", "COUNT"),
    ("bilqis.numeric/v1:school.op.SUCC", "numeric", "SUCC"),
)
EXPECTED_AXES = {
    "BOOL_NOT": ("boolean-input-polarity", "typed-answer-contrast"),
    "BOOL_AND": ("boolean-pair-combinations", "typed-answer-contrast"),
    "COUNT": ("entity-set-cardinality", "typed-answer-contrast"),
    "SUCC": ("numeric-successor-input", "typed-answer-contrast"),
}


def _grant(
    handle: str, evidence: str, *, release: str = RELEASE,
    revoked: bool = False,
) -> SourceGrant:
    return SourceGrant(
        handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, release, evidence,
        (PURPOSE,), (JURISDICTION,), (SCOPE,),
        rights_epoch=1, correction_generation=1, observed_at=2,
        effective_from=0, revoked=revoked)


def _source():
    entries = tuple(
        AbiEntry(index, 0, index, semantic_id, semantic_id,
                 "PRIOR_ACCEPTED_NATIVE_REGISTRY", True, True, "SOURCE_ADMITTED")
        for index, (semantic_id, _, _) in enumerate(FORMAL))
    bindings = (
        FormalDomainBinding(
            "boolean", "synthetic:boolean-source", "d" * 64,
            tuple(item[0] for item in FORMAL if item[1] == "boolean"),
            ("B.NOT", "B.AND")),
        FormalDomainBinding(
            "numeric", "synthetic:numeric-source", "e" * 64,
            tuple(item[0] for item in FORMAL if item[1] == "numeric"),
            ("C.COUNT", "C.SUCCESSOR")))
    return _resolve_from_bindings(
        bindings, entries, default_registry(RELEASE),
        semantic_release=RELEASE, atlas_bundle_id=BUNDLE)


def _case(
    operator_id: str, *values: tuple[str, object],
    release: str = RELEASE,
):
    registry = default_registry(release)
    task = TaskScope(
        PRINCIPAL, TENANT, PURPOSE, release, JURISDICTION, SCOPE,
        observed_frontier=3, effective_time=5, causal_prefix_end=20)
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        (PURPOSE,), (PUBLIC_FORMAL,), (JURISDICTION,), (SCOPE,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),))
    spec = registry.resolve(operator_id)
    grants = [_grant(
        "source:operator:" + operator_id, operator_grant_digest(spec),
        release=release)]
    operands = []
    typed = []
    for index, (type_name, value) in enumerate(values):
        handle = "source:literal:" + str(index)
        item = TypedValue(type_name, value, release, source_handle=handle)
        operand = SourceOperand(
            item, SourceKind.TASK_VISIBLE, "synthetic:source:" + str(index),
            visible_at_prefix=8)
        operands.append(operand)
        typed.append(item)
        grants.append(_grant(
            handle, source_operand_digest(operand), release=release))
    domain = None
    domain_handle = None
    if operator_id in ("COUNT", "SUCC"):
        domain = FiniteDomain(
            "synthetic:number", "v1", "Number",
            tuple(literal(str(index), "Number") for index in range(11)),
            SourceBinding(SourceLocator("synthetic", "v1", "numbers"), "f" * 64),
            codec=ValueCodec.DECIMAL_INTEGER_TEXT, closed=True)
        domain_handle = "source:numbers"
        grants.append(_grant(
            domain_handle, numeric_domain_digest(domain, release),
            release=release))
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda grant: grant.source_handle)))
    binding = OperatorBinding(
        task, frontier, policy, registry, tuple(operands),
        numeric_domain=domain, numeric_source_handle=domain_handle)
    return binding, tuple(typed)


def _selection():
    return AtlasArtifactSelection("synthetic", BUNDLE, RELEASE, SOURCE)


class FormalLessonTests(unittest.TestCase):
    def test_checker_rejects_mutated_admission_and_authority_metadata(self):
        binding, inputs = _case("SUCC", ("Number", 2))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            for field, forged in (
                    ("status", "ADAPTER_READY"),
                    ("learning_state", "LEARNING_VERIFIED"),
                    ("source_authority", "A13_TRANSFERABLE_AUTHORITY"),
                    ("schema", "forged/formal-lesson/v9")):
                with self.subTest(field=field):
                    lesson = construct_formal_lesson(
                        _selection(), FORMAL[3][0], inputs, binding)
                    object.__setattr__(lesson, field, forged)
                    with self.assertRaises(BilqisError) as caught:
                        check_formal_lesson(
                            lesson, lesson.positive, _selection(), binding)
                    self.assertEqual(
                        caught.exception.context["reason"],
                        "BAMF_FORMAL_LESSON_INVALID")

    def test_mutated_entity_set_cannot_be_reauthorized_by_new_grant(self):
        for malformed in (("alpha", "alpha"), ("beta", "alpha")):
            with self.subTest(malformed=malformed):
                binding, inputs = _case(
                    "COUNT", ("EntitySet", ("alpha", "beta")))
                object.__setattr__(inputs[0], "value", malformed)
                operand = binding.operands[0]
                grants = tuple(
                    replace(grant, evidence_digest=source_operand_digest(operand))
                    if grant.source_handle == inputs[0].source_handle else grant
                    for grant in binding.frontier.grants)
                binding = replace(
                    binding, frontier=replace(binding.frontier, grants=grants))
                with patch(
                        "bilqis_mlx.factory.formal_lessons."
                        "resolve_formal_source_operators",
                        return_value=_source()):
                    with self.assertRaises(BilqisError) as caught:
                        construct_formal_lesson(
                            _selection(), FORMAL[2][0], inputs, binding)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_FORMAL_LESSON_INPUT_INVALID")

    def test_mutated_typed_schema_cannot_be_reauthorized(self):
        binding, inputs = _case("SUCC", ("Number", 2))
        object.__setattr__(inputs[0], "schema_version", "forged/v9")
        grants = tuple(
            replace(grant, evidence_digest=source_operand_digest(
                binding.operands[0]))
            if grant.source_handle == inputs[0].source_handle else grant
            for grant in binding.frontier.grants)
        binding = replace(
            binding, frontier=replace(binding.frontier, grants=grants))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            with self.assertRaises(BilqisError) as caught:
                construct_formal_lesson(
                    _selection(), FORMAL[3][0], inputs, binding)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FORMAL_LESSON_INPUT_INVALID")

    def test_numeric_contrast_requires_another_source_admitted_value(self):
        binding, inputs = _case("COUNT", ("EntitySet", ("alpha", "beta")))
        single = replace(
            binding.numeric_domain, values=(literal("2", "Number"),))
        grants = tuple(
            replace(grant, evidence_digest=numeric_domain_digest(
                single, RELEASE))
            if grant.source_handle == binding.numeric_source_handle else grant
            for grant in binding.frontier.grants)
        restricted = replace(
            binding, numeric_domain=single,
            frontier=replace(binding.frontier, grants=grants))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            with self.assertRaises(BilqisError) as caught:
                construct_formal_lesson(
                    _selection(), FORMAL[2][0], inputs, restricted)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FORMAL_LESSON_CONTRAST_UNAVAILABLE")

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
            seen = {operator_id: set() for _, _, operator_id in FORMAL}
            for semantic_id, operator_id, operands, expected in (
                    (FORMAL[0][0], "BOOL_NOT", (("Boolean", True),), False),
                    (FORMAL[0][0], "BOOL_NOT", (("Boolean", False),), True),
                    (FORMAL[1][0], "BOOL_AND",
                     (("Boolean", True), ("Boolean", True)), True),
                    (FORMAL[1][0], "BOOL_AND",
                     (("Boolean", True), ("Boolean", False)), False),
                    (FORMAL[1][0], "BOOL_AND",
                     (("Boolean", False), ("Boolean", True)), False),
                    (FORMAL[1][0], "BOOL_AND",
                     (("Boolean", False), ("Boolean", False)), False),
                    (FORMAL[2][0], "COUNT",
                     (("EntitySet", ()),), 0),
                    (FORMAL[2][0], "COUNT",
                     (("EntitySet", ("alpha",)),), 1),
                    (FORMAL[2][0], "COUNT",
                     (("EntitySet", ("alpha", "beta")),), 2),
                    (FORMAL[2][0], "COUNT",
                     (("EntitySet", ("alpha", "beta", "gamma")),), 3),
                    (FORMAL[3][0], "SUCC", (("Number", 0),), 1),
                    (FORMAL[3][0], "SUCC", (("Number", 2),), 3),
                    (FORMAL[3][0], "SUCC", (("Number", 9),), 10)):
                with self.subTest(operator=operator_id):
                    binding, typed = _case(
                        operator_id, *operands, release=release.digest)
                    lesson = construct_formal_lesson(
                        selection, semantic_id, typed, binding)
                    self.assertEqual(lesson.positive.value, expected)
                    self.assertEqual(
                        lesson.variation_axes, EXPECTED_AXES[operator_id])
                    self.assertNotIn(lesson.evidence_sha256, seen[operator_id])
                    seen[operator_id].add(lesson.evidence_sha256)
                    self.assertTrue(check_formal_lesson(
                        lesson, lesson.positive, selection, binding))
                    self.assertFalse(check_formal_lesson(
                        lesson, lesson.contrast, selection, binding))
            self.assertEqual(
                {key: len(value) for key, value in seen.items()},
                {"BOOL_NOT": 2, "BOOL_AND": 4, "COUNT": 4, "SUCC": 3})

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
                        lesson.variation_axes, EXPECTED_AXES[operator_id])
                    self.assertEqual(lesson.status, FORMAL_LESSON_STATUS)
                    self.assertEqual(
                        lesson.learning_state, LEARNING_UNVERIFIED)
                    self.assertTrue(check_formal_lesson(
                        lesson, lesson.positive, _selection(), binding))
                    self.assertFalse(check_formal_lesson(
                        lesson, lesson.contrast, _selection(), binding))

    def test_variation_metadata_and_source_case_cannot_be_substituted(self):
        original, inputs = _case("BOOL_NOT", ("Boolean", True))
        changed, _ = _case("BOOL_NOT", ("Boolean", False))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            lesson = construct_formal_lesson(
                _selection(), FORMAL[0][0], inputs, original)
            forged_axes = replace(
                lesson, variation_axes=("boolean-pair-combinations",
                                        "typed-answer-contrast"))
            with self.assertRaises(BilqisError) as caught:
                check_formal_lesson(
                    forged_axes, lesson.positive, _selection(), original)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_FORMAL_LESSON_SOURCE_EVIDENCE_MISMATCH")
            with self.assertRaises(BilqisError):
                check_formal_lesson(
                    lesson, lesson.positive, _selection(), changed)

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


if __name__ == "__main__":
    unittest.main()
