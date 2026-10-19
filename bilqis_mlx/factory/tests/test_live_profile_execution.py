from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT.parent / "bilqis-mlx-retention-lab" / "vendor" / "legacy-v16"


@unittest.skipUnless(SOURCE.is_dir(), "Pinned historic source not mounted")
class LiveProfileExecutionTests(unittest.TestCase):
    def test_real_full_b_provider_executes_and_iff_profile_without_minimal_provider(self):
        code = textwrap.dedent(r'''
            from dataclasses import replace
            import hashlib
            import json
            from pathlib import Path

            from bilqis_mlx.boolean_composite import (
                build_course as build_composite, draw_composite)
            from bilqis_mlx.boolean_identification import (
                answer_heads as boolean_answer_heads,
                build_course as build_identification,
                draw_identification)
            from bilqis_mlx.factory.answers import (
                AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
                fixed_domain,
            )
            from bilqis_mlx.factory.curriculum_definition import from_legacy_course
            from bilqis_mlx.factory.execution import (
                CapabilityProfile, CurriculumProfile, GradeProfile,
                compile_execution_plan,
            )
            from bilqis_mlx.factory.executable_release import (
                ExecutableFactoryRelease, compile_executable_factory_release,
            )
            from bilqis_mlx.factory.generation import draw_execution_rows
            from bilqis_mlx.factory.live_releases import boolean_successor, initial_course
            from bilqis_mlx.grade_a_probe import read_sources
            from bilqis_mlx.grade_a_release import accepted_grade_a
            from bilqis_mlx.source_adapters.school import live_source_registry

            root = Path.cwd()
            source = root.parent / "bilqis-mlx-retention-lab" / "vendor" / "legacy-v16"
            manifest = json.loads((
                root / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
            course = initial_course(accepted_grade_a(manifest))
            course = boolean_successor(course, source)
            course = build_composite(course, source)
            course = build_identification(course, source)
            grade_b = replace(
                course.grades[-1],
                teaching_stages=(
                    tuple(cap.id for cap in course.grades[-1].capabilities[:6]),
                    ("B.COMPOSITE",),
                    ("B.IDBOOLOPS",),
                ))
            course = replace(course, grades=(course.grades[0], grade_b))
            curriculum, bindings = from_legacy_course(course)
            _, _, graph, _, _ = read_sources(source)
            digest = lambda value: hashlib.sha256(json.dumps(
                value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            assert digest(draw_composite(source, graph, seed=2026101902)) == (
                "7908f7fe4717948f9bf975905183b420e104b1add5a7f54def2e6f7fb81737b5")
            assert digest(draw_identification(source, graph, seed=2026101902)) == (
                "65a63389340617547f335d4d58a8a48a9e56985206bb8d98024e413bc9e01872")
            assert digest(boolean_answer_heads(graph)) == (
                "9f4d38c914cab64f1a242953541c56fb539a81cd1be277ea4aa2539d37af305f")
            registry = live_source_registry()
            answers = AnswerModalityRegistry((
                RegisteredAnswerModality(
                    AnswerModality("binary", "answer.binary/v1", "a" * 64),
                    fixed_domain(("FALSE", "TRUE")),
                    lambda value: {
                        "FALSE": "cogal.value.false",
                        "TRUE": "cogal.value.true",
                    }[value]),
                RegisteredAnswerModality(
                    AnswerModality(
                        "boolean_operator", "answer.boolean-operator/v1", "b" * 64),
                    fixed_domain(("NOT", "AND", "OR", "XOR", "IMPLIES", "IFF")),
                    lambda value: "cogal.operator." + value),
            ))
            profile = CurriculumProfile(
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
            plan = compile_execution_plan(
                curriculum,
                profile,
                registry,
                source_bindings=bindings,
                answer_registry=answers,
            )
            assert "source.micro.boolean-minimal/v1" not in {
                cap.provider_id for cap in plan.capabilities}
            assert plan.grade_map["B"].teaching_stages == (
                ("B.AND", "B.IFF"), ("B.COMPOSITE",), ("B.IDBOOLOPS",))

            rows = []
            for capability in plan.grade_map["B"].capabilities:
                rows.extend(draw_execution_rows(
                    source, graph, curriculum, plan, registry,
                    source_bindings=bindings,
                    seed=20261019, capability=capability))
            assert len(rows) == 48
            assert {row["capability"] for row in rows} == {
                "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"}
            composite = [row for row in rows if row["capability"] == "B.COMPOSITE"]
            identified = [row for row in rows if row["capability"] == "B.IDBOOLOPS"]
            assert {operator for row in composite for operator in row["operators"]} == {
                "AND", "IFF"}
            assert {row["gold"] for row in identified} == {"AND", "IFF"}
            assert all(tuple(row["operator_options"]) == ("AND", "IFF")
                       for row in identified)

            release = compile_executable_factory_release(
                curriculum, bindings, profile, registry, answers,
                source_root=source, graph=graph, verification_seed=2026101903,
                legacy_course=course)
            assert release.execution_plan == plan
            assert "source.micro.boolean-minimal/v1" not in {
                cap.provider_id for cap in release.execution_plan.capabilities}
            assert release.verification.assessments[-1].cumulative_scope == (
                *tuple(cap.id for cap in course.grades[0].capabilities),
                "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
            assert release.verification.assessments[-1].seal_sha256 != (
                plan.grade_map["B"].assessment_blueprint_sha256)
            restored = ExecutableFactoryRelease.from_manifest(
                json.loads(json.dumps(release.manifest())),
                release.release_sha256)
            assert restored == release
            print("LIVE_PROFILE_EXECUTION_OK")
        ''')
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], cwd=ROOT,
            capture_output=True, text=True, check=False)
        self.assertEqual(
            result.returncode, 0,
            msg="stdout:\n" + result.stdout + "\nstderr:\n" + result.stderr)
        self.assertIn("LIVE_PROFILE_EXECUTION_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
