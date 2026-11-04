from bilqis_mlx.factory.tests._executable_release_fixtures import *  # noqa: F403

class ExecutableFactoryReleaseTests(BaseExecutableFactoryReleaseTests):
    def test_semantic_footprint_is_runtime_only_and_preserves_release_identity(self):
        from unittest.mock import Mock
        baseline = self.compile()
        payload = json.dumps(baseline.manifest(), sort_keys=True)
        binding = self.bindings.bindings[0]
        original = self.registry.require(binding.generator_id, binding.oracle_id)
        callback = Mock(side_effect=lambda row:
                        ("z.op." + row["capability"].partition(".C")[2],))
        registered = replace(original, semantic_footprint=callback)
        self.registry = SourceAdapterRegistry((registered,))
        resolved = self.registry.require(binding.generator_id, binding.oracle_id)
        row = {"query": {"kind": "fixture"}, "capability": "Z.C0"}
        self.assertEqual(resolved.semantic_footprint(row), ("z.op.0",))
        callback.assert_called_once_with(row)
        callback.reset_mock()
        compiled = self.compile()
        self.assertEqual(json.dumps(compiled.manifest(), sort_keys=True), payload)
        self.assertEqual(compiled.release_sha256, baseline.release_sha256)
        restored = ExecutableFactoryRelease.from_manifest(
            json.loads(payload), baseline.release_sha256)
        self.assertEqual(restored, compiled)
        self.assertEqual(registered.descriptor, original.descriptor)
        self.assertEqual(callback.call_count, 24)

    def test_historical_registration_reads_but_v2_requires_a_footprint(self):
        baseline = self.compile()
        binding = self.bindings.bindings[0]
        adapter = replace(self.registry.require(binding.generator_id, binding.oracle_id),
                          semantic_footprint=None)
        self.registry = SourceAdapterRegistry((adapter,))
        self.assertIsNone(adapter.semantic_footprint)
        self.assertEqual(ExecutableFactoryRelease.from_manifest(
            baseline.manifest(), baseline.release_sha256), baseline)
        with self.assertRaisesRegex(ValueError, "CLOSURE:Z.C0:SOURCE_FOOTPRINT_UNAVAILABLE"):
            self.compile()
        self.registry.descriptors_for(self.course)
        for invalid in (False, "callback", (), {}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                    ValueError, "FACTORY_SOURCE_CONSTRUCTOR_AND_CHECKER_REQUIRED"):
                SourceAdapterRegistry((replace(adapter, semantic_footprint=invalid),))

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
