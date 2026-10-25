from dataclasses import replace
import json
import unittest

from bilqis_mlx.curriculum import BINARY, BOOLEAN_OPERATORS
from bilqis_mlx.factory.adapters import (
    RegisteredSourceAdapter, SourceAdapterRegistry,
)
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
    fixed_domain,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import (
    ExecutableFactoryRelease, compile_executable_factory_release,
)
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.execution import (
    CapabilityProfile, GradeProfile, PlanLineage,
)
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_boolean_course, _synthetic_course, _synthetic_registry,
)


def _answers():
    return AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/v1", "a" * 64),
            fixed_domain(BINARY),
            lambda value: {
                "FALSE": "cogal.value.false",
                "TRUE": "cogal.value.true",
            }[value]),
    ))


def _boolean_answers():
    return AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/v1", "a" * 64),
            fixed_domain(BINARY),
            lambda value: {
                "FALSE": "cogal.value.false",
                "TRUE": "cogal.value.true",
            }[value]),
        RegisteredAnswerModality(
            AnswerModality(
                "boolean_operator", "answer.boolean-operator/v1", "b" * 64),
            fixed_domain(BOOLEAN_OPERATORS),
            lambda value: "cogal.operator." + value),
    ))


class ExecutableFactoryReleaseTests(unittest.TestCase):
    def setUp(self):
        self.course = _synthetic_course(6)
        self.registry = _synthetic_registry()
        self.curriculum, self.bindings = from_legacy_course(self.course)
        self.answers = _answers()
        self.graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
            ],
        }

    def compile(self):
        return compile_executable_factory_release(
            self.curriculum,
            self.bindings,
            CurriculumProfile.full(),
            self.registry,
            self.answers,
            source_root=None,
            graph=self.graph,
            verification_seed=20261019,
        )

    def test_semantic_footprint_is_runtime_only_and_preserves_release_identity(self):
        from unittest.mock import Mock
        baseline = self.compile()
        payload = json.dumps(baseline.manifest(), sort_keys=True)
        binding = self.bindings.bindings[0]
        original = self.registry.require(binding.generator_id, binding.oracle_id)
        callback = Mock(return_value=("fixture.semantic.root",))
        registered = replace(original, semantic_footprint=callback)
        self.registry = SourceAdapterRegistry((registered,))
        resolved = self.registry.require(binding.generator_id, binding.oracle_id)
        row = {"query": {"kind": "fixture"}}
        self.assertEqual(resolved.semantic_footprint(row), ("fixture.semantic.root",))
        callback.assert_called_once_with(row)
        callback.reset_mock()
        compiled = self.compile()
        self.assertEqual(json.dumps(compiled.manifest(), sort_keys=True), payload)
        self.assertEqual(compiled.release_sha256, baseline.release_sha256)
        restored = ExecutableFactoryRelease.from_manifest(
            json.loads(payload), baseline.release_sha256)
        self.assertEqual(restored, compiled)
        self.assertEqual(registered.descriptor, original.descriptor)
        callback.assert_not_called()

    def test_historical_registration_keeps_optional_footprint_uninvoked(self):
        binding = self.bindings.bindings[0]
        adapter = self.registry.require(binding.generator_id, binding.oracle_id)
        self.assertIsNone(adapter.semantic_footprint)
        self.compile().verify()
        self.registry.descriptors_for(self.course)
        for invalid in (False, "callback", (), {}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    ValueError, "FACTORY_SOURCE_CONSTRUCTOR_AND_CHECKER_REQUIRED"):
                SourceAdapterRegistry((replace(adapter, semantic_footprint=invalid),))

    def test_full_graph_binding_rejects_same_catalog_substitution(self):
        from bilqis_mlx.factory.executable_release import _digest

        self.graph["nodes"] = [{"meaning": "é", "arity": 1}]
        release = self.compile()
        self.assertEqual(release.semantic_graph_sha256, _digest(self.graph))
        restored = ExecutableFactoryRelease.from_manifest(
            json.loads(json.dumps(release.manifest())), release.release_sha256)
        reordered = dict(reversed(tuple(self.graph.items())))
        restored.verify_semantic_catalog(reordered)
        changed = {**self.graph, "nodes": [{"meaning": "é", "arity": 2}]}
        with self.assertRaisesRegex(ValueError, "SEMANTIC_GRAPH_DRIFT"):
            restored.verify_semantic_catalog(changed)
        with self.assertRaisesRegex(ValueError, "SEMANTIC_GRAPH_INVALID"):
            replace(release, semantic_graph_sha256="invalid")

    def test_historical_v2_manifest_preserves_exact_hash_without_graph_field(self):
        from bilqis_mlx.factory.executable_release import _digest

        payload = json.loads(json.dumps(self.compile().manifest()))
        payload.pop("semantic_graph_sha256", None)
        historical_sha = "c37d62403c00e87b0cdd648764f5967eee9a58860941ddca694371f2544cf956"
        self.assertEqual(_digest(payload), historical_sha)
        restored = ExecutableFactoryRelease.from_manifest(payload, historical_sha)
        self.assertIsNone(restored.semantic_graph_sha256)
        self.assertNotIn("semantic_graph_sha256", restored.manifest())
        self.assertEqual(json.loads(json.dumps(restored.manifest())), payload)
        self.assertEqual(restored.expected_digest(), historical_sha)

    def test_compilers_reject_deleted_legacy_course_keyword(self):
        from bilqis_mlx.factory.executable_release import compile_successor_profile_release

        release = self.compile()
        with self.assertRaisesRegex(TypeError, "legacy_course"):
            compile_executable_factory_release(
                self.curriculum, self.bindings, CurriculumProfile.full(),
                self.registry, self.answers, source_root=None, graph=self.graph,
                verification_seed=17, legacy_course=self.course)
        with self.assertRaisesRegex(TypeError, "legacy_course"):
            compile_successor_profile_release(
                release, CurriculumProfile.full(), self.registry, self.answers,
                source_root=None, graph=self.graph, verification_seed=17,
                legacy_course=self.course)
        successor = compile_successor_profile_release(
            release, CurriculumProfile.full(), self.registry, self.answers,
            source_root=None, graph=self.graph, verification_seed=20261019)
        self.assertEqual(successor.verification, release.verification)
        self.assertEqual(successor.predecessor_release_sha256, release.release_sha256)

    def test_v2_release_roundtrips_complete_executable_authority(self):
        release = self.compile()
        release.verify()
        self.assertEqual(release.schema, "bilqis.mlx.factory-release/v2")
        self.assertEqual(
            release.execution_plan.curriculum_sha256,
            self.curriculum.digest())
        self.assertEqual(
            release.execution_plan.source_binding_sha256,
            self.bindings.digest())
        self.assertEqual(
            release.semantic_catalog_sha256,
            release.verification.semantic_catalog_sha256)
        self.assertEqual(
            tuple(item.kind for item in release.answer_modalities),
            ("binary",))
        self.assertEqual(
            tuple(item.capability_id for item in release.verification.capabilities),
            tuple(item.capability_id for item in release.execution_plan.capabilities))
        self.assertEqual(
            tuple(item.grade_id for item in release.verification.assessments),
            ("Z",))

        payload = json.loads(json.dumps(release.manifest()))
        restored = ExecutableFactoryRelease.from_manifest(
            payload, release.release_sha256)
        self.assertEqual(restored, release)
        restored.verify_semantic_catalog(self.graph)

    def compile_twelve(self):
        names = tuple(f"Z.C{i}" for i in range(12))
        template = self.curriculum.grades[0].capabilities[0]
        capabilities = tuple(replace(
            template, capability_id=name,
            taught_roots=(f"z.op.{i}",), examined_roots=(f"z.op.{i}",),
        ) for i, name in enumerate(names))
        grade = replace(self.curriculum.grades[0], capabilities=capabilities,
                        exam_item_counts=tuple((name, 4) for name in names))
        curriculum = replace(self.curriculum, grades=(grade,))
        bindings = replace(self.bindings, bindings=tuple(
            replace(self.bindings.bindings[0], capability_id=name) for name in names))
        return compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(), self.registry, self.answers,
            source_root=None, graph=self.graph, verification_seed=17)

    def test_twelve_capability_release_roundtrips_without_legacy_course(self):
        names = tuple(f"Z.C{i}" for i in range(12))
        release = self.compile_twelve()
        payload = json.loads(json.dumps(release.manifest()))
        self.assertEqual(payload["schema"], "bilqis.mlx.factory-release/v2")
        restored = ExecutableFactoryRelease.from_manifest(payload, release.release_sha256)
        restored.verify()
        restored.verify_semantic_catalog(self.graph)
        self.assertEqual(restored, release)
        self.assertEqual(restored.release_sha256, release.release_sha256)
        self.assertEqual(tuple(item.capability_id for item in restored.verification.capabilities), names)
        self.assertEqual(restored.verification.assessments[0].cumulative_scope, names)
        self.assertEqual(tuple(item.specimen_count for item in restored.verification.capabilities),
                         (4,) * 12)
        seal = restored.verification.assessments[0]
        self.assertEqual(len(seal.capability_receipt_sha256s), 12)
        self.assertEqual(restored.answer_heads[0].kind, "binary")
        self.assertEqual(restored.answer_heads[0].values, ("FALSE", "TRUE"))
        self.assertEqual(restored.answer_heads[0].token_ids, (1, 2))
        incomplete_seal = replace(seal, cumulative_scope=names[:-1],
                                  capability_receipt_sha256s=seal.capability_receipt_sha256s[:-1])
        incomplete_seal = replace(incomplete_seal, seal_sha256=incomplete_seal.expected_digest())
        mutations = (
            (replace(restored.verification, capabilities=restored.verification.capabilities[:-1]),
             "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DRIFT"),
            (replace(restored.verification, assessments=(incomplete_seal,)),
             "FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_DRIFT"),
        )
        for verification, error in mutations:
            with self.subTest(error=error):
                candidate = replace(restored, verification=verification)
                candidate = replace(candidate, release_sha256=candidate.expected_digest())
                with self.assertRaisesRegex(ValueError, f"^{error}$"):
                    candidate.verify()

    def test_twelve_capability_successors_preserve_existing_lineage_contract(self):
        predecessor = self.compile_twelve()
        variants = (
            (self.graph, "UNCHANGED"),
            ({"tokens": [*self.graph["tokens"], "fixture.appended"]}, "APPEND_ONLY_EXPANSION"),
        )
        for graph, geometry in variants:
            with self.subTest(geometry=geometry):
                successor = compile_executable_factory_release(
                    predecessor.curriculum, predecessor.source_bindings,
                    CurriculumProfile("fixture.successor"), self.registry, self.answers,
                    source_root=None, graph=graph, verification_seed=18, predecessor=predecessor)
                successor.verify_successor_of(predecessor)
                self.assertEqual(successor.predecessor_release_sha256, predecessor.release_sha256)
                delta = successor.transition
                self.assertEqual(delta.semantic_geometry, geometry)
                self.assertEqual(delta.previous_plan_sha256, predecessor.execution_plan.digest())
                self.assertEqual(delta.next_plan_sha256, successor.execution_plan.digest())
                self.assertEqual(delta.previous_curriculum_sha256, predecessor.curriculum.digest())
                self.assertEqual(delta.next_curriculum_sha256, predecessor.curriculum.digest())
                self.assertEqual(delta.previous_source_binding_sha256, predecessor.source_bindings.digest())
                self.assertEqual(delta.next_source_binding_sha256, predecessor.source_bindings.digest())
                self.assertEqual(delta.added_capabilities, ())
                self.assertEqual(delta.removed_capabilities, ())
                restored = ExecutableFactoryRelease.from_manifest(
                    json.loads(json.dumps(successor.manifest())), successor.release_sha256)
                restored.verify_successor_of(predecessor)
                self.assertEqual(restored.transition, delta)

    def test_v2_release_rejects_rehashed_plan_profile_mismatch(self):
        release = self.compile()
        mismatched = replace(
            release.execution_plan, profile_id="different-profile")
        candidate = replace(
            release, execution_plan=mismatched, release_sha256="0" * 64)
        candidate = replace(
            candidate, release_sha256=candidate.expected_digest())
        with self.assertRaisesRegex(
                ValueError, "FACTORY_EXECUTABLE_RELEASE_PROFILE_DRIFT"):
            candidate.verify()

    def test_v2_release_rejects_rehashed_provider_implementation_drift(self):
        release = self.compile()
        descriptor = release.source_adapters[0]
        changed = replace(descriptor, implementation_sha256="e" * 64)
        candidate = replace(
            release,
            source_adapters=(changed,),
            release_sha256="0" * 64)
        candidate = replace(
            candidate, release_sha256=candidate.expected_digest())
        with self.assertRaisesRegex(
                ValueError, "FACTORY_EXECUTABLE_RELEASE_PROVIDER_DRIFT"):
            candidate.verify()

    def test_v2_release_rejects_rehashed_verification_receipt_drift(self):
        release = self.compile()
        receipt = release.verification.capabilities[0]
        changed = replace(receipt, specimen_count=receipt.specimen_count + 1)
        verification = replace(
            release.verification,
            capabilities=(changed, *release.verification.capabilities[1:]))
        candidate = replace(
            release, verification=verification, release_sha256="0" * 64)
        candidate = replace(
            candidate, release_sha256=candidate.expected_digest())
        with self.assertRaisesRegex(
                ValueError, "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DRIFT"):
            candidate.verify()

    def test_profile_transition_binds_unchanged_geometry_and_new_assessment_seal(self):
        course, registry = _synthetic_boolean_course()
        curriculum, bindings = from_legacy_course(course)
        answers = _boolean_answers()
        graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                *(f"cogal.operator.{value}" for value in BOOLEAN_OPERATORS),
            ],
        }
        full = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            registry, answers, source_root=None, graph=graph,
            verification_seed=17)
        reduced_profile = CurriculumProfile(
            "boolean-kernel/and-iff",
            grades=(GradeProfile(
                "B",
                enabled_capabilities=(
                    "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"),
                capabilities=(
                    CapabilityProfile(
                        "B.COMPOSITE",
                        provider_parameters=(("operators", ("AND", "IFF")),)),
                    CapabilityProfile(
                        "B.IDBOOLOPS",
                        provider_parameters=(("operators", ("AND", "IFF")),),
                        answer_family_values=(
                            ("boolean_operator", ("AND", "IFF")),)),
                ),
            ),),
        )
        reduced = compile_executable_factory_release(
            curriculum, bindings, reduced_profile,
            registry, answers, source_root=None, graph=graph,
            verification_seed=17,
            predecessor=full)

        self.assertEqual(reduced.predecessor_release_sha256, full.release_sha256)
        self.assertEqual(reduced.transition.semantic_geometry, "UNCHANGED")
        self.assertEqual(
            reduced.transition.previous_curriculum_sha256,
            reduced.transition.next_curriculum_sha256)
        full_b = full.verification.assessments[-1]
        reduced_b = reduced.verification.assessments[-1]
        self.assertNotEqual(full_b.seal_sha256, reduced_b.seal_sha256)
        self.assertEqual(
            {item.provider_id for item in reduced.execution_plan.capabilities
             if item.grade_id == "B"},
            {"fixture.b-adapter/v1"})

    def test_source_oracle_failure_cannot_mint_verified_release(self):
        descriptor = self.registry.require(
            "fixture.z-generator/v1", "fixture.z-oracle/v1").descriptor
        failing_registry = SourceAdapterRegistry((
            RegisteredSourceAdapter(
                descriptor,
                self.registry.require(
                    "fixture.z-generator/v1", "fixture.z-oracle/v1").draw,
                lambda row, **_: False),
        ))
        with self.assertRaisesRegex(
                ValueError, "SOURCE_ORACLE_DISAGREEMENT"):
            compile_executable_factory_release(
                self.curriculum, self.bindings, CurriculumProfile.full(),
                failing_registry, self.answers,
                source_root=None, graph=self.graph,
                verification_seed=20261019)

    def test_incompatible_semantic_geometry_cannot_be_admitted(self):
        predecessor = self.compile()
        grade = self.course.grades[0]
        changed_capability = replace(
            grade.capabilities[-1],
            taught_roots=("fixture.changed",),
            examined_roots=("fixture.changed",))
        changed_course = replace(
            self.course,
            grades=(replace(
                grade,
                capabilities=(*grade.capabilities[:-1], changed_capability)),),
        )
        curriculum, bindings = from_legacy_course(changed_course)
        incompatible_graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.true",
                "cogal.value.false",
            ],
        }
        with self.assertRaisesRegex(
                ValueError, "INCOMPATIBLE_GEOMETRY"):
            compile_executable_factory_release(
                curriculum, bindings, CurriculumProfile.full(),
                self.registry, self.answers,
                source_root=None, graph=incompatible_graph,
                verification_seed=20261019,
                predecessor=predecessor)

    def test_append_only_semantic_geometry_is_carried_by_successor_release(self):
        predecessor = self.compile()
        grade = self.course.grades[0]
        new_capability = replace(
            grade.capabilities[-1],
            id="Z.C6",
            taught_roots=("fixture.op.6",),
            examined_roots=("fixture.op.6",))
        expanded_grade = replace(
            grade,
            capabilities=(*grade.capabilities, new_capability),
            exam_item_counts=(*grade.exam_item_counts, ("Z.C6", 4)))
        expanded_course = replace(self.course, grades=(expanded_grade,))
        curriculum, bindings = from_legacy_course(expanded_course)
        expanded_graph = {
            "tokens": [*self.graph["tokens"], "fixture.appended.identity"],
        }
        successor = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            self.registry, self.answers,
            source_root=None, graph=expanded_graph,
            verification_seed=20261019,
            predecessor=predecessor)

        self.assertEqual(
            successor.transition.semantic_geometry,
            "APPEND_ONLY_EXPANSION")
        self.assertEqual(
            successor.predecessor_release_sha256,
            predecessor.release_sha256)
        self.assertIn("Z.C6", successor.transition.added_capabilities)

    def test_rehashed_modality_descriptor_drift_is_rejected(self):
        release = self.compile()
        changed = replace(
            release.answer_modalities[0],
            implementation_sha256="f" * 64)
        candidate = replace(
            release,
            answer_modalities=(changed,),
            release_sha256="0" * 64)
        candidate = replace(
            candidate, release_sha256=candidate.expected_digest())
        with self.assertRaisesRegex(
                ValueError, "FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_DRIFT"):
            candidate.verify()

    def test_rehashed_semantic_catalog_binding_drift_is_rejected(self):
        release = self.compile()
        candidate = replace(
            release,
            semantic_catalog_sha256="f" * 64,
            release_sha256="0" * 64)
        candidate = replace(
            candidate, release_sha256=candidate.expected_digest())
        with self.assertRaisesRegex(
                ValueError, "FACTORY_EXECUTABLE_RELEASE_CATALOG_DRIFT"):
            candidate.verify()

    def test_loaded_semantic_catalog_must_match_release_answer_bindings(self):
        release = self.compile()
        changed = {
            "tokens": [
                "fixture.padding",
                "cogal.value.true",
                "cogal.value.false",
            ],
        }
        with self.assertRaisesRegex(
                ValueError, "FACTORY_EXECUTABLE_RELEASE_CATALOG_DRIFT"):
            release.verify_semantic_catalog(changed)


if __name__ == "__main__":
    unittest.main()
