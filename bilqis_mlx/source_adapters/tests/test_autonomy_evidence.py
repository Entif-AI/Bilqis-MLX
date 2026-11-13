from pathlib import Path
import json
import unittest

from bilqis_mlx.factory.autonomy import (
    EvidenceKind, EvidenceObligation, obligations_for_capability,
)
from bilqis_mlx.factory.evidence import draw_evidence_rows
from bilqis_mlx.factory.live_releases import (
    boolean_composite_successor, boolean_identification_successor,
    boolean_successor, compile_live_release, numeric_successor,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.live_grade_c import REGISTRY_COUNTING_TARGET, registry_graph
from bilqis_mlx.runtime.autonomy_live import build_live_autonomy_plan


ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "vendor" / "legacy-v16"


class LiveMicroAutonomyEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LEGACY.is_dir():
            raise unittest.SkipTest("pinned finite-micro source unavailable")
        grade_a = accepted_grade_a(json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
        cls.course = boolean_successor(grade_a, LEGACY)
        cls.release = compile_live_release(cls.course)
        _, _, cls.graph, _, _ = read_sources(LEGACY)
        cls.registry = live_source_registry()

    def test_live_boolean_adapter_has_no_a_operand_obligations(self):
        plan = build_live_autonomy_plan(self.release, LEGACY)
        obligations = obligations_for_capability(
            self.release, "B.AND", plan=plan)
        self.assertFalse(any(
            required.startswith("A.")
            for obligation in obligations
            for required in obligation.requires_capabilities))

    def test_live_boolean_capability_declares_no_a_prerequisite(self):
        self.assertEqual(self.course.capability_map["B.AND"].prerequisites, ())

    def test_numeric_adapter_witnesses_declared_prerequisite_transfer(self):
        composite = boolean_composite_successor(self.course, LEGACY)
        identified = boolean_identification_successor(composite, LEGACY)
        numeric, _ = numeric_successor(
            identified, maximum=REGISTRY_COUNTING_TARGET)
        release = compile_live_release(numeric)
        obligation = EvidenceObligation(
            obligation_id="C.ADD/prerequisite/C.SUCCESSOR",
            capability_id="C.ADD",
            kind=EvidenceKind.PREREQUISITE,
            key="C.SUCCESSOR",
            minimum_specimens=1,
            generation_axes=("source-valid", "fresh-seed"),
            requires_capabilities=("C.SUCCESSOR",),
        )
        rows = draw_evidence_rows(
            LEGACY, registry_graph(), release, self.registry,
            obligation, seed=20261019)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["capability"], "C.ADD")
        self.assertEqual(rows[0]["lesson_id"], "LESSON-060")

    def test_numeric_factory_admission_binds_semantics_and_exact_provider(self):
        from unittest.mock import patch
        from bilqis_mlx.factory.curriculum_definition import from_legacy_course
        from bilqis_mlx.factory.execution import CurriculumProfile
        from bilqis_mlx.factory.executable_release import (
            ExecutableFactoryRelease, compile_executable_factory_release,
        )
        from bilqis_mlx.factory.generation import runtime_adapter_for_release
        from bilqis_mlx.factory.live_answers import live_answer_registry
        composite = boolean_composite_successor(self.course, LEGACY)
        identified = boolean_identification_successor(composite, LEGACY)
        numeric, graph = numeric_successor(identified, maximum=REGISTRY_COUNTING_TARGET)
        curriculum, bindings = from_legacy_course(numeric)
        def compile_with(registry):
            return compile_executable_factory_release(
                curriculum, bindings, CurriculumProfile.full(), registry,
                live_answer_registry(), source_root=LEGACY, graph=graph,
                verification_seed=19)
        original = compile_with(live_source_registry())
        manifest = original.manifest()
        source_file = ROOT / "bilqis_mlx/source_adapters/numeric.py"
        read_bytes = Path.read_bytes
        def refactored_bytes(path):
            value = read_bytes(path)
            return value + b"\n# semantics-preserving provider revision\n" if path == source_file else value
        with patch.object(Path, "read_bytes", refactored_bytes):
            registry = live_source_registry()
            revised = compile_with(registry)
        self.assertEqual(original.semantic_catalog_sha256, revised.semantic_catalog_sha256)
        self.assertIsNotNone(original.semantic_graph_sha256)
        self.assertEqual(original.semantic_graph_sha256, revised.semantic_graph_sha256)
        self.assertEqual(original.source_bindings, revised.source_bindings)
        self.assertNotEqual(original.verification.provider_descriptors_sha256,
                            revised.verification.provider_descriptors_sha256)
        self.assertNotEqual(original.release_sha256, revised.release_sha256)
        self.assertEqual(original.manifest(), manifest)
        restored = ExecutableFactoryRelease.from_manifest(manifest, original.release_sha256)
        self.assertEqual(restored.manifest(), manifest)
        from copy import deepcopy
        from bilqis_mlx.generated_assessment import digest
        for field in ("semantic_catalog_sha256", "implementation_sha256"):
            incomplete = deepcopy(manifest)
            target = incomplete if field == "semantic_catalog_sha256" else incomplete["source_adapters"][-1]
            del target[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                ExecutableFactoryRelease.from_manifest(incomplete, digest(incomplete))
        for field in ("semantic_catalog_sha256", "implementation_sha256"):
            stale = deepcopy(manifest)
            target = stale if field == "semantic_catalog_sha256" else stale["source_adapters"][-1]
            target[field] = "f" * 64
            with self.subTest(stale=field), self.assertRaises(ValueError):
                ExecutableFactoryRelease.from_manifest(stale, digest(stale))
        execution = next(item for item in original.execution_plan.capabilities
                         if item.capability_id == "C.ADD")
        with self.assertRaisesRegex(ValueError, "FACTORY_EXECUTABLE_GENERATION_ADAPTER_DRIFT"):
            runtime_adapter_for_release(LEGACY, graph, original, registry, execution)
        current = next(item for item in revised.execution_plan.capabilities
                       if item.capability_id == "C.ADD")
        self.assertIs(runtime_adapter_for_release(LEGACY, graph, revised, registry, current),
                      registry.require(bindings.by_capability["C.ADD"].generator_id,
                                       bindings.by_capability["C.ADD"].oracle_id))


if __name__ == "__main__":
    unittest.main()
