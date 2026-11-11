"""C16.2b fail-closed custody checks for the C05-owned BAMF fixed school."""
from __future__ import annotations

import json
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.tests.bamf_first_student._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


class BamfFactoryFixedSchoolSafetyTests(BamfFirstStudentCase):
    def test_c05_bamf_fixed_school_rejects_receipt_provenance_tamper(self):
        target = self.root / "c05-native-fixed-school-tamper"
        self.preflight(target)
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            bind_accepted_execution_cache,
            load_accepted_generation,
        )
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner
        import json

        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=_synthetic_registry()), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=_answers()), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            parent = load_accepted_generation(target)
            cache = bind_accepted_execution_cache(target)
            fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

        receipt_path = (
            target / "c05-fixed-school" / f"{parent.run_identity.digest}.json")
        receipt = json.loads(receipt_path.read_text())
        receipt["foundation_parent_manifest_sha256"] = "f" * 64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaises(BilqisError), shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

    def test_c05_bamf_fixed_school_rejects_receipt_scope_and_pointer_drift(self):
        target = self.root / "c05-native-fixed-school-drift"
        self.preflight(target)
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            bind_accepted_execution_cache,
            load_accepted_generation,
        )
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner
        import json

        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=_synthetic_registry()), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=_answers()), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            parent = load_accepted_generation(target)
            cache = bind_accepted_execution_cache(target)
            fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

        receipt_path = (
            target / "c05-fixed-school" / f"{parent.run_identity.digest}.json")
        original = json.loads(receipt_path.read_text())
        mutations = {
            "extra-key": lambda value: value.__setitem__("extra", "forbidden"),
            "missing-key": lambda value: value.pop("rubric_sha256"),
            "invalid-type": lambda value: value.__setitem__("seed", None),
            "release": lambda value: value.__setitem__(
                "factory_release_sha256", "a" * 64),
            "source": lambda value: value.__setitem__(
                "source_identity_sha256", "a" * 64),
            "catalog": lambda value: value.__setitem__(
                "semantic_catalog_sha256", "a" * 64),
            "scope": lambda value: value.__setitem__(
                "capabilities", value["capabilities"][:-1]),
            "pointer": lambda value: value.__setitem__(
                "cohort_file", "cohorts/" + "a" * 64 + ".json"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                changed = json.loads(json.dumps(original))
                mutate(changed)
                receipt_path.write_text(json.dumps(changed))
                with self.assertRaises(BilqisError), shape_patch():
                    fixed_owner._bamf_fixed_school_cohort(
                        context, target,
                        expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
                receipt_path.write_text(json.dumps(original))

    def test_c05_bamf_fixed_school_anchor_missing_or_symlink_fails_closed(self):
        target = self.root / "c05-native-fixed-school-anchor-tamper"
        self.preflight(target)
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner

        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=_synthetic_registry()), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=_answers()), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            cache = bind_accepted_execution_cache(target)
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        anchor = target / ".c05-fixed-school.anchor.json"
        original = anchor.read_text()
        anchor.unlink()
        with self.assertRaises(BilqisError), shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        anchor.write_text(original)
        anchor.unlink()
        anchor.symlink_to(target / "bamf-state.json")
        with self.assertRaises(BilqisError), shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

    def test_c05_bamf_fixed_school_rejects_cohort_content_tamper(self):
        target = self.root / "c05-native-fixed-school-cohort-tamper"
        self.preflight(target)
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            bind_accepted_execution_cache,
            load_accepted_generation,
        )
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner
        import json

        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=_synthetic_registry()), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=_answers()), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            parent = load_accepted_generation(target)
            cache = bind_accepted_execution_cache(target)
            fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

        receipt_path = (
            target / "c05-fixed-school" / f"{parent.run_identity.digest}.json")
        receipt = json.loads(receipt_path.read_text())
        cohort_path = target / receipt["cohort_file"]
        cohort = json.loads(cohort_path.read_text())
        cohort["seed"] += 1
        cohort_path.write_text(json.dumps(cohort))
        with self.assertRaises((BilqisError, ValueError)), shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)

    def test_c05_bamf_fixed_school_rejects_unsafe_selector_directory_before_draw(self):
        target = self.root / "c05-native-fixed-school-unsafe"
        self.preflight(target)
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            bind_accepted_execution_cache,
            load_accepted_generation,
        )
        import bilqis_mlx.runtime.factory_fixed_school as fixed_owner

        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=_synthetic_registry()), patch(
                "bilqis_mlx.factory.live_answers.live_answer_registry",
                return_value=_answers()), shape_patch():
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.graph, source_root=None)
            parent = load_accepted_generation(target)
            cache = bind_accepted_execution_cache(target)
        selector = target / "c05-fixed-school"
        selector.mkdir()
        (selector / "foreign.json").write_text("{}")
        with patch.object(
                fixed_owner, "_draw_executable_scope_cohort",
                side_effect=AssertionError("unsafe custody reached source draw")), shape_patch():
            with self.assertRaises(BilqisError):
                fixed_owner._bamf_fixed_school_cohort(
                    context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)



if __name__ == "__main__":
    import unittest
    unittest.main()
