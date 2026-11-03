"""Thin phase orchestration for one source-grounded teaching visit."""
from __future__ import annotations

from types import SimpleNamespace

from . import finalization, preparation, retention, step_training


def take_visit(d, mx, run_dir, receipt, manifest, course, engine, params, optimizer, graph,
               *, steps_per_visit, batch_size, reserve_gib, source_root=None,
               learning_settings=None, boolean_association_bridge=False,
               source_prefetch_executor=None, source_prefetch_workers=0,
               autonomy_teaching_option=None, capture_teacher_observations=True):
    s = SimpleNamespace(
        mx=mx, run_dir=run_dir, receipt=receipt, manifest=manifest, course=course,
        engine=engine, params=params, optimizer=optimizer, graph=graph,
        steps_per_visit=steps_per_visit, batch_size=batch_size, reserve_gib=reserve_gib,
        source_root=source_root, learning_settings=learning_settings,
        boolean_association_bridge=boolean_association_bridge,
        source_prefetch_executor=source_prefetch_executor,
        source_prefetch_workers=source_prefetch_workers,
        autonomy_teaching_option=autonomy_teaching_option,
        capture_teacher_observations=capture_teacher_observations)
    early = preparation.prepare(d, s)
    if early is not None:
        return early
    step_training.run(d, s)
    retention.evaluate(d, s)
    return finalization.finalize(d, s)
