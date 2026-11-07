"""Live-profile subprocess fixture: boolean profile."""
PROBE = r'''profile = CurriculumProfile(
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
    source_root=source, graph=graph, verification_seed=2026101903)
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

release_rows = []
for capability in release.execution_plan.grade_map["B"].capabilities:
    release_rows.extend(draw_executable_release_rows(
        source, graph, release, registry,
        seed=20261019,
        capability=capability))
assert release_rows == rows
release_heads = answer_heads_from_executable_release(
    release, graph)
assert release_heads["boolean_operator"]["values"] == ["AND", "IFF"]
typed = prepare_typed_batches(
    [row for row in release_rows
     if row["capability"] == "B.IDBOOLOPS"],
    release_heads)
assert typed["boolean_operator"]["gold_labels"]
assert set(typed["boolean_operator"]["gold_labels"]) == {
    "AND", "IFF"}

'''
