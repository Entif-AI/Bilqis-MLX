"""C16.2b integrity attacks against the C05-owned BAMF fixed school."""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.tests.bamf_first_student._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


class BamfFactoryFixedSchoolIntegrityTests(BamfFirstStudentCase):
    def _context(self, target):
        from unittest.mock import patch
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

        sources, answers = _synthetic_registry(), _answers()
        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=sources), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=answers), shape_patch():
            host = AcceptedRuntimeHost(target)
            context = host.source_context(graph=self.graph, source_root=None)
            cache = bind_accepted_execution_cache(target)
        return host, context, cache, sources, answers

    def test_cold_school_rejects_content_valid_subset_relabelled_as_whole_scope(self):
        target = self.root / "c05-subset-substitution"
        self.preflight(target)
        _host, context, cache, _sources, _answers = self._context(target)
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner
        from bilqis_mlx.generated_assessment import make_cohort

        with shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        receipt_path = next((target / "c05-fixed-school").glob("*.json"))
        receipt = json.loads(receipt_path.read_text())
        cohort_path = target / receipt["cohort_file"]
        stored = json.loads(cohort_path.read_text())
        kept = stored["capabilities"][0]
        rows = [row for row in stored["rows"] if row["capability"] == kept]
        forged = make_cohort(
            rows,
            generator_version=stored["generator_version"],
            seed=stored["seed"],
            rubric_version=stored["rubric_sha256"],
        )
        stored["rows"] = rows
        stored["cohort_sha256"] = forged.digest
        forged_path = target / "cohorts" / f"{forged.digest}.json"
        forged_path.write_text(json.dumps(stored, sort_keys=True, separators=(",", ":")))
        receipt["cohort_sha256"] = forged.digest
        receipt["cohort_file"] = str(forged_path.relative_to(target))
        receipt_path.write_text(json.dumps(receipt))

        with self.assertRaises(BilqisError), shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

    def test_fixed_school_rejects_valid_but_wrong_persisted_factory_release(self):
        target = self.root / "c05-wrong-valid-release"
        self.preflight(target)
        host, _context, cache, sources, answers = self._context(target)
        from bilqis_mlx.factory.executable_release import compile_successor_profile_release
        from bilqis_mlx.factory.execution import CurriculumProfile
        from bilqis_mlx.runtime.admission import _persist_executable_factory_release
        from bilqis_mlx.runtime.source_execution import SourceExecutionContext
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner

        successor = compile_successor_profile_release(
            self.release, CurriculumProfile.full(), sources, answers,
            source_root=None, graph=self.graph, verification_seed=20261111)
        self.assertNotEqual(successor.release_sha256, self.release.release_sha256)
        release_file = _persist_executable_factory_release(target, successor)
        with shape_patch():
            wrong = SourceExecutionContext.from_admitted_release(
                target,
                {"factory_release_sha256": successor.release_sha256,
                 "factory_release_file": release_file},
                graph=self.graph, source_root=None,
                source_registry=sources, answer_registry=answers,
                accepted_runtime_host=host)
            with self.assertRaises(BilqisError):
                fixed_owner._bamf_fixed_school_cohort(
                    wrong, target,
                    expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

    def test_source_binding_digest_fallback_is_receipt_and_cohort_authority(self):
        from dataclasses import replace
        from bilqis_mlx.factory.curriculum_definition import SourceBindingSet
        from bilqis_mlx.factory.executable_release import compile_executable_factory_release
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.learning.champions import Checkpoint
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.admission import _executable_factory_admission
        from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
        from bilqis_mlx.runtime.state import _fingerprint
        from bilqis_mlx.state_dag import persist
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner

        sources, answers = _synthetic_registry(), _answers()
        bindings = SourceBindingSet(self.release.source_bindings.bindings, None)
        release = compile_executable_factory_release(
            self.release.curriculum, bindings, self.release.profile, sources, answers,
            source_root=None, graph=self.graph, verification_seed=20261112)
        source = self.root / "fallback-source"
        origin = Checkpoint("7" * 64, "bundles/foundation-origin", 0, True)
        _, release_file, admission = _executable_factory_admission(
            source, release, origin, _fingerprint(self.graph), self.graph)
        persist(source, {
            "generation": 0, "factory_release_sha256": release.release_sha256,
            "factory_release_file": release_file,
            "factory_admission_v2": asdict(admission),
            "semantic_graph_sha256": _fingerprint(self.graph),
            "school": {"current_student": asdict(origin)},
        })
        target = self.root / "fallback-target"
        config = replace(self.config(run_id="c05-source-fallback"), source_run_dir=str(source))
        self.preflight(target, config=config, release=release)
        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=sources), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=answers), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            cache = bind_accepted_execution_cache(target)
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        receipt = json.loads(next((target / "c05-fixed-school").glob("*.json")).read_text())
        self.assertEqual(receipt["source_identity_sha256"], bindings.digest())
        cohort = json.loads((target / receipt["cohort_file"]).read_text())
        self.assertEqual(cohort["source_manifest_sha256"], bindings.digest())

    def test_first_materialization_after_generation_one_keeps_run_stable_school(self):
        from unittest.mock import patch
        import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate, publish_bamf_generation
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            bind_accepted_execution_cache, load_accepted_generation,
        )
        from bilqis_mlx.runtime.bamf_bundle.package_import_transition import (
            _issue_package_import_transition,
        )
        from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import acceptance
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner

        target = self.root / "c05-generation-one-first-materialization"
        self.preflight(target)

        def advance(tag):
            with shape_patch():
                parent = load_accepted_generation(target)
                cache = bind_accepted_execution_cache(target)
            transition = _issue_package_import_transition(
                package_sha256=tag * 64, screened_candidate_sha256="2" * 64,
                reset_policy_sha256="3" * 64, c05_evidence_sha256="4" * 64,
                c05_policy_sha256="5" * 64, source_clearance_sha256="6" * 64)
            successor = BamfBundleCandidate(
                parent.run_id, parent.generation + 1, cache.accepted_manifest_sha256,
                parent.implementation_sha256, parent.topology, parent.extents,
                parent.retained_state, parent.optimizer_hyperparameters,
                parent.provenance, parent.semantic_abi, parent.compiler_features,
                parent.correction_frontier, parent.teacher_state,
                parent.evaluation_contract, transition,
                ({"event": "BAMF_PACKAGE_IMPORT_ACCEPTED",
                  "optimizer_step": parent.retained_state.optimizer_step},),
                parent.run_identity)
            with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                    patch("bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom"):
                pointer = publish_bamf_generation(
                    target, successor,
                    acceptance=acceptance(successor, parent=parent.retained_state),
                    reserve_gib=0.)
            return pointer

        first = advance("1")
        sources, answers = _synthetic_registry(), _answers()
        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=sources), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=answers), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            cache = bind_accepted_execution_cache(target)
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        receipt_path = next((target / "c05-fixed-school").glob("*.json"))
        original = json.loads(receipt_path.read_text())
        self.assertEqual(original["foundation_parent_manifest_sha256"], first["manifest_sha256"])

        advance("7")
        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=sources), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=answers), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            cache = bind_accepted_execution_cache(target)
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        cold = json.loads(receipt_path.read_text())
        self.assertEqual(cold["seed"], original["seed"])
        self.assertEqual(cold["cohort_sha256"], original["cohort_sha256"])
        self.assertEqual(
            cold["foundation_parent_manifest_sha256"],
            original["foundation_parent_manifest_sha256"])


if __name__ == "__main__":
    import unittest
    unittest.main()
