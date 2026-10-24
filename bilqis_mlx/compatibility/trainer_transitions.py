"""Historical Course transition entry points delegated to runtime owners."""
from __future__ import annotations

import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption

def activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    return _runtime_release_adoption._activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def activate_revised_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    return _runtime_release_adoption._activate_revised_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def activate_replaced_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    return _runtime_release_adoption._activate_replaced_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def _auto_adopt_known_grade_boundary(
        mx, run_dir, receipt, course, grade_a_course, source_root, manifest,
        parameters, optimizer, graph, *, reserve_gib, full_grade_b,
        numeric_staircase):
    """Compatibility entry point for runtime-owned boundary policy."""
    return _runtime_release_adoption._auto_adopt_known_grade_boundary(
        mx, run_dir, receipt, course, grade_a_course, source_root, manifest,
        parameters, optimizer, graph, reserve_gib=reserve_gib,
        full_grade_b=full_grade_b, numeric_staircase=numeric_staircase)
