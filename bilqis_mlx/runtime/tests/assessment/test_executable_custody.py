from bilqis_mlx.runtime.tests._executable_assessment_fixtures import *  # noqa: F403

class ExecutableAssessmentTests(BaseExecutableAssessmentTests):
    def test_unrelated_profile_change_preserves_exact_a_cohort_identity(self):
        full, full_contract = self.draw(self.full, self.a_scope)
        reduced, reduced_contract = self.draw(
            self.reduced, reversed(self.a_scope))

        self.assertEqual(full_contract.rubric_sha256,
                         reduced_contract.rubric_sha256)
        self.assertEqual(full_contract.source_sha256,
                         reduced_contract.source_sha256)
        self.assertEqual(full.digest, reduced.digest)
        self.assertEqual(full.rows, reduced.rows)
        self.assertNotEqual(full_contract.factory_release_sha256,
                            reduced_contract.factory_release_sha256)

    def test_exact_scope_persists_and_cold_reads_with_separate_identities(self):
        cohort, contract = self.draw(
            self.reduced, (*self.a_scope, "B.AND", "B.IFF"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            restored = _load_executable_cohort(
                root, self.manifest, self.reduced,
                contract.capabilities, pointer)

            self.assertEqual(restored, cohort)
            payload = json.loads((root / pointer["cohort_file"]).read_text())
            self.assertEqual(payload["rubric_sha256"], contract.rubric_sha256)
            self.assertEqual(payload["source_sha256"], contract.source_sha256)
            self.assertEqual(
                payload["factory_release_sha256"],
                self.reduced.release_sha256)
            self.assertNotEqual(
                payload["rubric_sha256"],
                payload["factory_release_sha256"])

    def test_recent_v2_exact_scope_exam_is_a_valid_live_rubric_authority(self):
        cohort, contract = self.draw(self.reduced, ("B.IDBOOLOPS",))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release_path = _persist_executable_factory_release(root, self.reduced)
            pointer = _persist_executable_cohort(root, self.manifest, contract, cohort)
            receipt = {
                "factory_release_sha256": self.reduced.release_sha256,
                "factory_release_file": release_path,
                "factory_admission_v2": {},
                "source_manifest_sha256": self.manifest["manifest_sha256"],
                "live_rubric_sha256": contract.rubric_sha256,
                "last_exam": {**pointer, "exam_rubric_sha256": contract.rubric_sha256},
            }
            program = SimpleNamespace(grades=(SimpleNamespace(
                assessment_sha256="f" * 64),))
            self.assertIsNone(_verify_live_rubric_lineage(root, receipt, program))
            with self.assertRaises(ValueError):
                _verify_live_rubric_lineage(root, {
                    **receipt, "last_exam": {**receipt["last_exam"],
                       "cohort_sha256": "0" * 64}}, program)
            with self.assertRaisesRegex(ValueError, "LIVE_RUBRIC_IDENTITY_DRIFT"):
                _verify_live_rubric_lineage(root, {
                    **receipt, "live_rubric_sha256": "e" * 64}, program)

    def test_v2_cohort_replays_as_championship_evidence_with_exact_rubric(self):
        cohort, contract = self.draw(self.reduced, self.a_scope)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            restored = load_championship_cohort(root, {
                "cohort_sha256": cohort.digest,
                "rubric_sha256": contract.rubric_sha256,
                "cohort_rubric_sha256": contract.rubric_sha256,
                "source_oracle_sha256": self.manifest["manifest_sha256"],
            })
        self.assertEqual(restored, cohort)

    def test_current_pointer_rejects_holistic_release_change_even_when_scope_matches(self):
        cohort, contract = self.draw(self.full, self.a_scope)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_EXECUTABLE_COHORT_RELEASE_DRIFT"):
                _load_executable_cohort(
                    root, self.manifest, self.reduced,
                    self.a_scope, pointer)

    def test_content_tamper_is_rejected(self):
        cohort, contract = self.draw(self.reduced, ("B.IDBOOLOPS",))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            path = root / pointer["cohort_file"]
            payload = json.loads(path.read_text())
            payload["rows"][0]["gold"] = (
                "IFF" if payload["rows"][0]["gold"] == "AND" else "AND")
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_EXECUTABLE_COHORT_CONTENT_DRIFT"):
                _load_executable_cohort(
                    root, self.manifest, self.reduced,
                    ("B.IDBOOLOPS",), pointer)
