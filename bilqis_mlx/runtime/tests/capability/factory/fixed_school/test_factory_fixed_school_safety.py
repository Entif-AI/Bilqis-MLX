"""C16.2b fail-closed custody checks for the C05-owned BAMF fixed school."""
from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.tests.bamf_first_student._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


class BamfFactoryFixedSchoolSafetyTests(BamfFirstStudentCase):
    def test_c05_bamf_fixed_school_repairs_receipt_provenance_tamper(self):
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
        original = json.loads(receipt_path.read_text())
        changed = dict(original)
        changed["foundation_parent_manifest_sha256"] = "f" * 64
        receipt_path.write_text(json.dumps(changed))
        with shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        self.assertEqual(json.loads(receipt_path.read_text()), original)

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
                with shape_patch():
                    fixed_owner._bamf_fixed_school_cohort(
                        context, target,
                        expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
                self.assertEqual(json.loads(receipt_path.read_text()), original)

    def test_c05_bamf_fixed_school_trust_row_is_append_only(self):
        target = self.root / "c05-native-fixed-school-trust-tamper"
        self.preflight(target)
        from bilqis_mlx.factory.tests.test_executable_release import _answers
        from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_registry
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.bamf_bundle.admission import (
            bind_accepted_execution_cache, load_accepted_generation,
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
            fixed_owner._bamf_fixed_school_cohort(
                context, target,
                expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        from bilqis_mlx.data_plane import data_plane
        plane = data_plane()
        with plane._lock:
            with self.assertRaises(sqlite3.IntegrityError):
                plane._db.execute(
                    "UPDATE bamf_c05_fixed_school_trust SET run_id='forged' "
                    "WHERE run_identity_sha256=?", (parent.run_identity.digest,))
            with self.assertRaises(sqlite3.IntegrityError):
                plane._db.execute(
                    "DELETE FROM bamf_c05_fixed_school_trust "
                    "WHERE run_identity_sha256=?", (parent.run_identity.digest,))

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
        original = json.loads(cohort_path.read_text())
        cohort["seed"] += 1
        cohort_path.write_text(json.dumps(cohort))
        with shape_patch():
            fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        self.assertEqual(json.loads(cohort_path.read_text()), original)

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
        selector.symlink_to(target / "bamf-state.json")
        with shape_patch():
            with self.assertRaises(BilqisError):
                fixed_owner._bamf_fixed_school_cohort(
                    context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        selector.unlink()
        with patch.object(
                fixed_owner, "_draw_executable_scope_cohort",
                side_effect=AssertionError("retry redrew after trust publication")), shape_patch():
            recovered = fixed_owner._bamf_fixed_school_cohort(
                context, target, expected_parent_manifest_sha256=cache.accepted_manifest_sha256)
        self.assertTrue(recovered.rows)

    def test_c05_projection_fd_cannot_be_redirected_by_live_ancestor_swap(self):
        from bilqis_mlx.runtime._factory_fixed_school_io import (
            fixed_school_root, project_bytes,
        )

        accepted_parent = self.root / "accepted-parent"
        accepted_run = accepted_parent / "run"
        accepted_run.mkdir(parents=True)
        outside_parent = self.root / "outside-parent"
        (outside_parent / "run").mkdir(parents=True)
        moved_parent = self.root / "accepted-parent-moved"
        raw = b'{"trusted":true}'

        with self.assertRaises(BilqisError):
            with fixed_school_root(accepted_run) as (root_fd, _identity):
                accepted_parent.rename(moved_parent)
                accepted_parent.symlink_to(outside_parent, target_is_directory=True)
                project_bytes(root_fd, "cohorts", "trusted.json", raw)

        self.assertEqual(
            (moved_parent / "run" / "cohorts" / "trusted.json").read_bytes(), raw)
        self.assertFalse(
            (outside_parent / "run" / "cohorts" / "trusted.json").exists())



if __name__ == "__main__":
    import unittest
    unittest.main()
