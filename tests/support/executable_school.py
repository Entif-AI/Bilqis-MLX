"""Bind disposable historical fixtures through the production v2 migration."""


def admit_executable_school(run_dir, receipt, course, grade_a, source_root, graph):
    from bilqis_mlx import trainer

    receipt, release, program = trainer._ensure_executable_release(
        run_dir, receipt, course, grade_a, source_root, graph)
    receipt = trainer._migrate_championship_governance(run_dir, receipt, course)
    return receipt, release, program
