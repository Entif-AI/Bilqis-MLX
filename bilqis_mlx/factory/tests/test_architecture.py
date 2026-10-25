from pathlib import Path
import tempfile
import unittest

from scripts.check_factory_architecture import inspect_factory_architecture


ROOT = Path(__file__).resolve().parents[3]


class FactoryArchitectureTests(unittest.TestCase):
    def test_semantic_identity_dispatch_is_confined_to_registration_owners(self):
        concrete = "from bilqis_mlx import live_grade_d\n"
        branch = "def route(cap):\n    if cap == 'D.NEW':\n        return 1\n"
        release = ("from somewhere import NUMERIC_RELEASE as selected\n"
                   "def route(value):\n    return value == selected\n")
        fixtures = (
            ("runtime/leaf.py", concrete, True),
            ("runtime/leaf.py", "from ..live_grade_d import generate\n", True),
            ("factory/consumer.py", branch, True),
            ("learning/consumer.py", branch, True),
            ("runtime/leaf.py", release, True),
            ("runtime/leaf.py", "def route(cap):\n    match cap:\n        case 'D.NEW': return 1\n", True),
            ("runtime/leaf.py", "adapter_id = 'D.NEW'\nsource_sense_id = 'sense'\n", False),
            ("factory/adapters.py", concrete + branch, False),
            ("factory/candidate_realizations.py", concrete + branch, False),
            ("source_adapters/domain.py", concrete + branch, False),
            ("compatibility/history.py", concrete + branch, False),
            ("research/prototype.py", concrete + branch, False),
        )
        for relative, source, rejected in fixtures:
            with self.subTest(path=relative, source=source), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "bilqis_mlx/factory").mkdir(parents=True)
                path = root / "bilqis_mlx" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
                findings = inspect_factory_architecture(root)
                identity_findings = [item for item in findings if any(code in item for code in (
                    "GENERIC_IMPORTS_CONCRETE_PROVIDER", "GENERIC_CAPABILITY_IDENTITY_DISPATCH",
                    "GENERIC_RELEASE_IDENTITY_REFERENCE"))]
                self.assertEqual(bool(identity_findings), rejected)

    def test_v2_cardinality_is_independent_of_the_legacy_course_ceiling(self):
        from bilqis_mlx.curriculum import AnswerFamily, Capability, Course, Grade, validate
        from bilqis_mlx.factory.curriculum_definition import (
            CapabilitySpec, CurriculumDefinition, GradeSpec, validate_curriculum_definition)

        answers = (AnswerFamily("binary", ("FALSE", "TRUE")),)
        for count in (0, 1, 9, 10, 12, 13):
            with self.subTest(contract="v2", count=count):
                caps = tuple(CapabilitySpec(f"Z.C{i}", "foundation", (f"root.{i}",),
                                           (f"root.{i}",), (), (), answers)
                             for i in range(count))
                definition = CurriculumDefinition("fixture", (GradeSpec(
                    "Z", caps, tuple((cap.capability_id, 12) for cap in caps)),))
                if 1 <= count <= 12:
                    validate_curriculum_definition(definition, answer_kinds=("binary",))
                else:
                    with self.assertRaisesRegex(ValueError, "^FACTORY_CURRICULUM_GRADE_INVALID$"):
                        validate_curriculum_definition(definition, answer_kinds=("binary",))
        for count in (1, 9, 10):
            with self.subTest(contract="legacy", count=count):
                caps = tuple(Capability(f"Z.C{i}", "foundation", "repo:fixture",
                                        (f"root.{i}",), (f"root.{i}",), (), (), answers)
                             for i in range(count))
                course = Course((Grade("Z", caps),), "fixture")
                if count <= 9:
                    validate(course)
                else:
                    with self.assertRaisesRegex(ValueError, "^GRADE_CAPABILITY_COUNT_OUTSIDE_SIX_TO_NINE$"):
                        validate(course)

    def test_compatibility_cannot_call_current_mutation_owners(self):
        self.assertFalse((ROOT / "bilqis_mlx/compatibility/trainer_transitions.py").exists())
        writers = (
            ("admission", "_factory_admission"),
            ("admission", "_executable_factory_admission"),
            ("checkpoints", "_advance"),
            ("checkpoints", "_persist"),
            ("checkpoints", "_reconcile_delivery_outbox"),
            ("release_adoption", "_adopt_executable_profile"),
            ("release_adoption", "_adopt_catalog_profile"),
        )
        for owner, name in writers:
            module = f"bilqis_mlx.runtime.{owner}"
            sources = (
                f"import {module}\n{module}.{name}()\n",
                f"import {module} as owner\nowner.{name}()\n",
                f"from {module} import {name}\n{name}()\n",
                f"from {module} import {name} as write\nwrite()\n",
                f"from bilqis_mlx.runtime import {owner} as owner\nowner.{name}()\n",
                f"from ..runtime.{owner} import {name} as write\nwrite()\n",
                f"from ..runtime import {owner}\n{owner}.{name}()\n",
                f"from {module} import *\n{name}()\n",
            )
            for source in sources:
                with self.subTest(owner=owner, source=source), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    (root / "bilqis_mlx/factory").mkdir(parents=True)
                    (root / "bilqis_mlx/compatibility").mkdir()
                    (root / "bilqis_mlx/compatibility/history.py").write_text(source)
                    findings = inspect_factory_architecture(root)
                    self.assertTrue(any("COMPATIBILITY_CALLS_CURRENT_WRITER" in item
                                        and f"{module}.{name}" in item for item in findings))

    def test_compatibility_may_decode_verify_and_construct_records(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/compatibility").mkdir()
            (root / "bilqis_mlx/compatibility/history.py").write_text(
                "from bilqis_mlx.runtime.checkpoints import _with_delivery_outbox\n"
                "from bilqis_mlx.runtime import admission\n"
                "from external import _advance\n"
                "_with_delivery_outbox()\nadmission.verify_identity()\n_advance()\n"
                "decode_state()\nderive_schedule()\nverify_executable_release()\n"
                "measure_debt_boundary()\n")
            self.assertFalse(any("COMPATIBILITY_CALLS_CURRENT_WRITER" in item
                                 for item in inspect_factory_architecture(root)))

    def test_current_api_cannot_accept_or_forward_legacy_course(self):
        sources = (
            "def generate(*, legacy_course=None):\n    return ()\n",
            "def generate():\n    return build(legacy_course=historical)\n",
            "def generate():\n    return context.legacy_course\n",
        )
        for source in sources:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "bilqis_mlx/factory").mkdir(parents=True)
                (root / "bilqis_mlx/factory/generation.py").write_text(source)
                self.assertTrue(any("CURRENT_API_USES_LEGACY_COURSE" in problem
                                    for problem in inspect_factory_architecture(root)))

    def test_historical_decoder_may_read_legacy_course(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/compatibility").mkdir()
            (root / "bilqis_mlx/compatibility/decode.py").write_text(
                "def decode(legacy_course):\n    return legacy_course\n")
            self.assertFalse(any("CURRENT_API_USES_LEGACY_COURSE" in problem
                                 for problem in inspect_factory_architecture(root)))

    def test_current_repository_has_no_factory_bypass(self):
        self.assertEqual(inspect_factory_architecture(ROOT), ())

    def test_retired_current_transition_cannot_be_restored_or_reexported(self):
        for source in (
            "def activate_numeric_grade(): pass\n",
            "from somewhere import next_grade_readiness\n",
        ):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "bilqis_mlx/factory").mkdir(parents=True)
                (root / "bilqis_mlx/grade_transition.py").write_text(source)
                self.assertTrue(any("RETIRED_CURRENT_TRANSITION" in item
                                    for item in inspect_factory_architecture(root)))

    def test_future_grade_runtime_fork_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/__init__.py").write_text("")
            (root / "bilqis_mlx/live_grade_d.py").write_text("GRADE = 'D'\n")
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n _require_factory_admission()\n"
                "def _activate_next_admitted_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/grade_transition.py").write_text(
                "# Historical evidence digests only.\n")
            (root / "bilqis_mlx/numeric_staircase.py").write_text(
                "def _rebind():\n _factory_admission()\n")
            problems = inspect_factory_architecture(root)
            self.assertTrue(any("FUTURE_GRADE_RUNTIME_FORK:D" in item for item in problems))

    def test_generic_grade_letter_dispatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/__init__.py").write_text(
                "def route(grade):\n    if grade == 'B':\n        return 1\n")
            (root / "bilqis_mlx/live_curriculum.py").write_text("")
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n _require_factory_admission()\n"
                "def _activate_next_admitted_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/grade_transition.py").write_text(
                "# Historical evidence digests only.\n")
            (root / "bilqis_mlx/numeric_staircase.py").write_text(
                "def _rebind():\n _factory_admission()\n")
            problems = inspect_factory_architecture(root)
            self.assertTrue(any("GENERIC_GRADE_IDENTITY_DISPATCH B" in item for item in problems))

    def test_training_entrypoint_without_release_gate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/__init__.py").write_text("")
            (root / "bilqis_mlx/live_curriculum.py").write_text("")
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n pass\n"
                "def _activate_next_admitted_grade():\n _factory_admission()\n")
            (root / "bilqis_mlx/grade_transition.py").write_text(
                "# Historical evidence digests only.\n")
            (root / "bilqis_mlx/numeric_staircase.py").write_text(
                "def _rebind():\n _factory_admission()\n")
            problems = inspect_factory_architecture(root)
            self.assertIn(
                "bilqis_mlx/trainer.py OPERATE_BYPASSES_FACTORY_RELEASE",
                problems)

    def test_training_entrypoint_with_v2_release_gate_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/__init__.py").write_text("")
            (root / "bilqis_mlx/live_curriculum.py").write_text("")
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n _ensure_executable_release()\n"
                "def _adopt_executable_profile():\n"
                " _require_executable_factory_admission()\n"
                " _executable_factory_admission()\n")
            (root / "bilqis_mlx/grade_transition.py").write_text(
                "# Historical evidence digests only.\n")
            (root / "bilqis_mlx/numeric_staircase.py").write_text(
                "def _rebind():\n _factory_admission()\n")
            self.assertEqual(inspect_factory_architecture(root), ())

    def test_legacy_release_gate_does_not_authorize_current_training(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/trainer.py").write_text(
                "def operate():\n _require_factory_admission()\n")
            self.assertIn("bilqis_mlx/trainer.py OPERATE_BYPASSES_FACTORY_RELEASE",
                          inspect_factory_architecture(root))

    def test_leaf_service_cannot_import_the_trainer_facade(self):
        imports = (
            "from bilqis_mlx import trainer\n",
            "import bilqis_mlx.trainer as facade\n",
            "from bilqis_mlx.trainer import operate\n",
            "from .. import trainer\n",
            "from ..trainer import operate\n",
        )
        for name in ("leaf.py", "trainer.py", "cli.py", "__init__.py"):
            for source in imports:
                with self.subTest(name=name, source=source), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    (root / "bilqis_mlx/factory").mkdir(parents=True)
                    (root / "bilqis_mlx/runtime").mkdir()
                    (root / "bilqis_mlx/runtime" / name).write_text(source)
                    self.assertTrue(any("LEAF_IMPORTS_TRAINER" in problem
                                        for problem in inspect_factory_architecture(root)))

    def test_leaf_service_may_import_an_unrelated_trainer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/factory/leaf.py").write_text(
                "from external import trainer\nfrom external.trainer import train\n")
            self.assertFalse(any("LEAF_IMPORTS_TRAINER" in problem
                                 for problem in inspect_factory_architecture(root)))

    def test_facade_cannot_hide_an_ungated_service(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bilqis_mlx/factory").mkdir(parents=True)
            (root / "bilqis_mlx/runtime").mkdir()
            (root / "bilqis_mlx/trainer.py").write_text(
                "from bilqis_mlx.runtime.loop import operate\n"
                "def _adopt_executable_profile():\n _executable_factory_admission()\n")
            (root / "bilqis_mlx/runtime/loop.py").write_text("def operate():\n pass\n")
            self.assertTrue(any("OPERATE_BYPASSES_FACTORY_RELEASE" in problem
                                for problem in inspect_factory_architecture(root)))


if __name__ == "__main__":
    unittest.main()
