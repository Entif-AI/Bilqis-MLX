from bilqis_mlx.factory.tests._executable_release_fixtures import *  # noqa: F403

class ExecutableFactoryReleaseTests(BaseExecutableFactoryReleaseTests):
    def test_twelve_capability_successors_preserve_existing_lineage_contract(self):
        predecessor = self.compile_twelve()
        variants = (
            (self.graph, "UNCHANGED"),
            ({"tokens": [*self.graph["tokens"], "fixture.appended"]}, "APPEND_ONLY_EXPANSION"),
        )
        for graph, geometry in variants:
            with self.subTest(geometry=geometry):
                successor = compile_executable_factory_release(
                    predecessor.curriculum, predecessor.source_bindings,
                    CurriculumProfile("fixture.successor"), self.registry, self.answers,
                    source_root=None, graph=graph, verification_seed=18, predecessor=predecessor)
                successor.verify_successor_of(predecessor)
                self.assertEqual(successor.predecessor_release_sha256, predecessor.release_sha256)
                delta = successor.transition
                self.assertEqual(delta.semantic_geometry, geometry)
                self.assertEqual(delta.previous_plan_sha256, predecessor.execution_plan.digest())
                self.assertEqual(delta.next_plan_sha256, successor.execution_plan.digest())
                self.assertEqual(delta.previous_curriculum_sha256, predecessor.curriculum.digest())
                self.assertEqual(delta.next_curriculum_sha256, predecessor.curriculum.digest())
                self.assertEqual(delta.previous_source_binding_sha256, predecessor.source_bindings.digest())
                self.assertEqual(delta.next_source_binding_sha256, predecessor.source_bindings.digest())
                self.assertEqual(delta.added_capabilities, ())
                self.assertEqual(delta.removed_capabilities, ())
                restored = ExecutableFactoryRelease.from_manifest(
                    json.loads(json.dumps(successor.manifest())), successor.release_sha256)
                restored.verify_successor_of(predecessor)
                self.assertEqual(restored.transition, delta)

    def test_profile_transition_binds_unchanged_geometry_and_new_assessment_seal(self):
        course, registry = _synthetic_boolean_course()
        curriculum, bindings = from_legacy_course(course)
        answers = _boolean_answers()
        graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                *(f"cogal.operator.{value}" for value in BOOLEAN_OPERATORS),
            ],
        }
        full = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            registry, answers, source_root=None, graph=graph,
            verification_seed=17)
        reduced_profile = CurriculumProfile(
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
        reduced = compile_executable_factory_release(
            curriculum, bindings, reduced_profile,
            registry, answers, source_root=None, graph=graph,
            verification_seed=17,
            predecessor=full)

        self.assertEqual(reduced.predecessor_release_sha256, full.release_sha256)
        self.assertEqual(reduced.transition.semantic_geometry, "UNCHANGED")
        self.assertEqual(
            reduced.transition.previous_curriculum_sha256,
            reduced.transition.next_curriculum_sha256)
        full_b = full.verification.assessments[-1]
        reduced_b = reduced.verification.assessments[-1]
        self.assertNotEqual(full_b.seal_sha256, reduced_b.seal_sha256)
        self.assertEqual(
            {item.provider_id for item in reduced.execution_plan.capabilities
             if item.grade_id == "B"},
            {"fixture.b-adapter/v1"})

    def test_incompatible_semantic_geometry_cannot_be_admitted(self):
        predecessor = self.compile()
        grade = self.course.grades[0]
        changed_capability = replace(
            grade.capabilities[-1],
            taught_roots=("fixture.changed",),
            examined_roots=("fixture.changed",))
        changed_course = replace(
            self.course,
            grades=(replace(
                grade,
                capabilities=(*grade.capabilities[:-1], changed_capability)),),
        )
        curriculum, bindings = from_legacy_course(changed_course)
        incompatible_graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.true",
                "cogal.value.false",
            ],
        }
        with self.assertRaisesRegex(
                ValueError, "INCOMPATIBLE_GEOMETRY"):
            compile_executable_factory_release(
                curriculum, bindings, CurriculumProfile.full(),
                self.registry_with_revised_roots({"Z.C5": "fixture.changed"}), self.answers,
                source_root=None, graph=incompatible_graph,
                verification_seed=20261019,
                predecessor=predecessor)

    def test_append_only_semantic_geometry_is_carried_by_successor_release(self):
        predecessor = self.compile()
        grade = self.course.grades[0]
        new_capability = replace(
            grade.capabilities[-1],
            id="Z.C6",
            taught_roots=("fixture.op.6",),
            examined_roots=("fixture.op.6",))
        expanded_grade = replace(
            grade,
            capabilities=(*grade.capabilities, new_capability),
            exam_item_counts=(*grade.exam_item_counts, ("Z.C6", 4)))
        expanded_course = replace(self.course, grades=(expanded_grade,))
        curriculum, bindings = from_legacy_course(expanded_course)
        expanded_graph = {
            "tokens": [*self.graph["tokens"], "fixture.appended.identity"],
        }
        successor = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            self.registry_with_revised_roots({"Z.C6": "fixture.op.6"}), self.answers,
            source_root=None, graph=expanded_graph,
            verification_seed=20261019,
            predecessor=predecessor)

        self.assertEqual(
            successor.transition.semantic_geometry,
            "APPEND_ONLY_EXPANSION")
        self.assertEqual(
            successor.predecessor_release_sha256,
            predecessor.release_sha256)
        self.assertIn("Z.C6", successor.transition.added_capabilities)
