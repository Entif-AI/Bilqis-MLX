from bilqis_mlx.factory.tests._executable_release_fixtures import *  # noqa: F403

class ExecutableFactoryReleaseTests(BaseExecutableFactoryReleaseTests):
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
