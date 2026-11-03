"""Live-profile subprocess fixture: projection."""
PROBE = r'''historical_minimal = minimal_boolean_successor(grade_a, source)
a_curriculum, a_bindings, a_profile, a_canonical = (
    project_legacy_course(
        grade_a, grade_a, source,
        answer_kinds=answers.kinds))
assert a_profile.grades[0].enabled_capabilities == ()
assert tuple(grade.grade_id for grade in a_curriculum.grades) == (
    "A", "B", "C")
a_plan = compile_execution_plan(
    a_curriculum, a_profile, registry,
    source_bindings=a_bindings,
    answer_registry=answers)
assert tuple(grade.grade_id for grade in a_plan.grades) == ("A",)

projected_curriculum, projected_bindings, projected_profile, projected_course = (
    project_legacy_course(
        historical_minimal, grade_a, source,
        answer_kinds=answers.kinds))
assert projected_curriculum.digest() == a_curriculum.digest()
assert projected_bindings.digest() == a_bindings.digest()
assert tuple(
    cap.capability_id
    for cap in projected_curriculum.grades[1].capabilities
) == (
    "B.NOT", "B.AND", "B.OR", "B.XOR",
    "B.IMPLIES", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
assert projected_profile.grades[0].enabled_capabilities == (
    "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
projected_plan = compile_execution_plan(
    projected_curriculum, projected_profile, registry,
    source_bindings=projected_bindings,
    answer_registry=answers)
assert tuple(
    projected_plan.grade_map["B"].capabilities
) == ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")
assert "source.micro.boolean-minimal/v1" not in {
    cap.provider_id for cap in projected_plan.capabilities}
projected_release = compile_executable_factory_release(
    projected_curriculum, projected_bindings, projected_profile,
    registry, answers, source_root=source, graph=graph,
    verification_seed=2026101904)
assert projected_release.execution_plan == projected_plan

'''
