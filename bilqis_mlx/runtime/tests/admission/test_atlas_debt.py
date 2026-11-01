"""Native manifest debt projection; disposable metadata, no learner execution."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.runtime.atlas_debt import read_native_atlas_debt
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.tests.test_admission import _executable_fixture
from bilqis_mlx.errors import BilqisError


class AtlasDebtTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.release, self.graph = _executable_fixture()
        self.student = Checkpoint('e' * 64, 'bundles/disposable', 0, True)
        program = schedule_program_from_executable_release(self.release)
        school = replace(start_new(program, self.student), carried_mastery_debt=('Z.C0',),
                         mature_capability_debt=(('Z.C1', 2),), mature_grade_debt=(('Z', 3),))
        _, path, admission = _executable_factory_admission(
            self.root, self.release, self.student, _fingerprint(self.graph), self.graph)
        self.receipt = dict(run_id='disposable', generation=2,
            factory_release_sha256=self.release.release_sha256, factory_release_file=path,
            factory_admission_v2=asdict(admission), semantic_graph_sha256=_fingerprint(self.graph),
            school=asdict(school))

    def read(self, receipt=None, digest=None):
        receipt = self.receipt if receipt is None else receipt
        return read_native_atlas_debt(self.root, receipt, self.graph,
            expected_manifest_sha256=digest or _fingerprint(receipt))

    def test_all_native_debt_survives_with_exact_release_scope_and_no_mutation(self):
        before = deepcopy(self.receipt)
        files = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.read()
        self.assertEqual(result.carried_mastery_debt, ('Z.C0',))
        self.assertEqual(result.mature_capability_debt, (('Z.C1', 2),))
        self.assertEqual(result.mature_grade_debt, (('Z', 3),))
        self.assertEqual(result.capability_grades[0], ('Z.C0', 'Z'))
        self.assertEqual(result.profile_sha256, _fingerprint(asdict(self.release.profile)))
        self.assertEqual(result.current_provider_parameters,
            tuple((c.capability_id, c.provider_parameters) for c in self.release.execution_plan.capabilities))
        self.assertEqual(result.historical_scope_policy_status, 'NOT_MEASURED')
        self.assertEqual(result, self.read())
        self.assertEqual(self.receipt, before)
        self.assertEqual(files, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_missing_debt_fields_are_not_silently_empty(self):
        for name in ('carried_mastery_debt', 'mature_capability_debt', 'mature_grade_debt'):
            receipt = deepcopy(self.receipt)
            del receipt['school'][name]
            with self.subTest(name=name), self.assertRaises(BilqisError):
                self.read(receipt)

    def test_changed_generation_unknown_debt_and_student_drift_reject(self):
        receipt = deepcopy(self.receipt)
        receipt['generation'] += 1
        with self.assertRaises(BilqisError):
            self.read(receipt, _fingerprint(self.receipt))
        for field, value in (('carried_mastery_debt', ('FUTURE',)),
                             ('current_student', asdict(replace(self.student, sha256='f' * 64)))):
            receipt = deepcopy(self.receipt)
            receipt['school'][field] = value
            with self.subTest(field=field), self.assertRaises((BilqisError, ValueError)):
                self.read(receipt)

    def test_legacy_migration_and_empty_debt_remain_distinct(self):
        receipt = deepcopy(self.receipt)
        receipt['school']['mature_grade_debt'] = ()
        with self.assertRaises(BilqisError) as caught:
            self.read(receipt)
        self.assertEqual(caught.exception.context['reason'], 'BAMF_ATLAS_NATIVE_DEBT_MIGRATION_REQUIRED')
        for name in ('carried_mastery_debt', 'mature_capability_debt', 'mature_grade_debt'):
            receipt['school'][name] = ()
        result = self.read(receipt)
        self.assertEqual(result.carried_mastery_debt, ())
        self.assertEqual(result.mature_capability_debt, ())
        self.assertEqual(result.mature_grade_debt, ())
        self.assertEqual(result.historical_scope_policy_status, 'NOT_MEASURED')
        self.assertFalse(result.authorizes_learning)
