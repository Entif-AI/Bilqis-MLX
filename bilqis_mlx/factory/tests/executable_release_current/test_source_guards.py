from bilqis_mlx.factory.tests._executable_release_fixtures import *  # noqa: F403

class ExecutableFactoryReleaseTests(BaseExecutableFactoryReleaseTests):
    def test_seal_rejects_a_source_true_unintroduced_constituent(self):
        binding = self.bindings.bindings[0]
        adapter = self.registry.require(binding.generator_id, binding.oracle_id)
        self.registry = SourceAdapterRegistry((replace(
            adapter, semantic_footprint=lambda row: ("future.root",)),))
        with self.assertRaisesRegex(
                ValueError, "FACTORY_INSTRUCTIONAL_CONSTITUENT_CLOSURE:Z.C0:future.root"):
            self.compile()

    def test_untyped_source_footprint_fails_closed(self):
        adapter = self.registry.require("fixture.z-generator/v1", "fixture.z-oracle/v1")
        self.registry = SourceAdapterRegistry((replace(adapter, semantic_footprint=lambda row: "z.op.0"),))
        with self.assertRaisesRegex(ValueError, "CLOSURE:Z.C0:SOURCE_FOOTPRINT_INVALID"):
            self.compile()

    def test_normal_v2_draw_checks_new_rows_after_safe_sealing(self):
        from bilqis_mlx.factory.generation import draw_executable_release_rows
        binding = self.bindings.bindings[0]
        adapter = self.registry.require(binding.generator_id, binding.oracle_id)
        self.registry = SourceAdapterRegistry((replace(adapter, semantic_footprint=lambda row:
            ("z.op." + row["capability"].partition(".C")[2],)),))
        release = self.compile()
        changed = SourceAdapterRegistry((replace(
            adapter, semantic_footprint=lambda row: ("future.root",)),))
        with self.assertRaisesRegex(
                ValueError, "FACTORY_INSTRUCTIONAL_CONSTITUENT_CLOSURE:Z.C0:future.root"):
            draw_executable_release_rows(None, self.graph, release, changed,
                                         seed=99, capability="Z.C0", each=4)

    def test_instructional_closure_uses_only_target_prior_grade_and_earlier_stage(self):
        original_grade = self.curriculum.grades[0]
        prior_cap = replace(original_grade.capabilities[0], capability_id="Y.C0",
                            taught_roots=("prior.root",), examined_roots=("prior.root",))
        prior = replace(original_grade, grade_id="Y", capabilities=(prior_cap,),
                        exam_item_counts=(("Y.C0", 4),))
        current = replace(original_grade, teaching_stages=(
            ("Z.C0",), tuple(cap.capability_id for cap in original_grade.capabilities[1:])))
        self.curriculum = replace(self.curriculum, grades=(prior, current))
        self.bindings = replace(self.bindings, bindings=(
            replace(self.bindings.bindings[0], capability_id="Y.C0"), *self.bindings.bindings))
        adapter = self.registry.require(self.bindings.bindings[0].generator_id,
                                        self.bindings.bindings[0].oracle_id)
        def roots(row):
            cap = row["capability"]
            if cap == "Y.C0":
                return ("prior.root",)
            if cap == "Z.C1":
                return ("prior.root", "z.op.0", "z.op.1")
            return ("z.op." + cap.partition(".C")[2],)
        self.registry = SourceAdapterRegistry((replace(adapter, semantic_footprint=roots),))
        self.compile().verify()
        for target in ("Z.C0", "Z.C2"):
            self.registry = SourceAdapterRegistry((replace(adapter, semantic_footprint=lambda row:
                ("z.op.1",) if row["capability"] == target else roots(row)),))
            with self.subTest(target=target), self.assertRaisesRegex(
                    ValueError, "CLOSURE:" + target + ":z.op.1"):
                self.compile()
        self.registry = SourceAdapterRegistry((replace(adapter, semantic_footprint=roots),))
        with self.assertRaisesRegex(ValueError, "CLOSURE:Z.C1:prior.root"):
            compile_executable_factory_release(
                self.curriculum, self.bindings, CurriculumProfile("no-prior", (
                    GradeProfile("Y", enabled_capabilities=()),)), self.registry, self.answers,
                source_root=None, graph=self.graph, verification_seed=17)

    def test_source_oracle_failure_cannot_mint_verified_release(self):
        descriptor = self.registry.require(
            "fixture.z-generator/v1", "fixture.z-oracle/v1").descriptor
        failing_registry = SourceAdapterRegistry((
            RegisteredSourceAdapter(
                descriptor,
                self.registry.require(
                    "fixture.z-generator/v1", "fixture.z-oracle/v1").draw,
                lambda row, **_: False),
        ))
        with self.assertRaisesRegex(
                ValueError, "SOURCE_ORACLE_DISAGREEMENT"):
            compile_executable_factory_release(
                self.curriculum, self.bindings, CurriculumProfile.full(),
                failing_registry, self.answers,
                source_root=None, graph=self.graph,
                verification_seed=20261019)
