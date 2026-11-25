"""Focused reference parity and owner-boundary adversaries for #1617."""
from __future__ import annotations

import json
import os
from pathlib import Path


def _case_projection(item):
    compiled = item.compiled_case
    return (item.case, compiled.task_template, compiled.compiled_rows,
            compiled.compiler_configs, compiled.source_asts,
            compiled.partial_forest_receipts, item.source_row,
            item.prevalidated_exact_result)


def scope_smoke(run, d):
    """Exercise actual training lowering and C05 compilation before a long run."""
    from types import SimpleNamespace
    from bilqis_mlx.runtime import factory_candidate_microbatch as training
    from bilqis_mlx.runtime import factory_complete_solver as evaluation
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
    from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
    from scripts.bamf.profiling.issue1617.scope import install_scope

    d.h.require(run.resolve() != (d.h.ROOT.parent / 'aspirant').resolve(), 'sovereign run prohibited')
    d.h.require(Path(os.environ['BILQIS_DATA_PLANE']).resolve() == (run.parent / 'plane.sqlite3').resolve(), 'wrong smoke plane')
    with evidence_mode(strict=False):
        parent, context, artifact, _ = _execution_context(run)
        feature = context._accepted_feature_context
        rows = tuple(context.draw_rows(seed=17, capability='A.PARENT', each=2))
        d.h.require(len(rows) == 2, 'smoke source rows missing')
        compiled = SimpleNamespace(
            sources=(SimpleNamespace(source_row=rows[0]),),
            compiled=SimpleNamespace(features=feature.features))
        recorder = d.Recorder()
        recorder.install()

        def train():
            return training._learning_first_task_goals(context, compiled)

        def assess():
            instruments = evaluation.factory_evaluation_instruments(
                source_context=context, candidate=parent, artifact_path=str(artifact),
                rows=rows, seed=17, each=2, release_prevalidated=True,
                authenticated=feature)
            return tuple(_case_projection(item) for item in instruments)

        reference, reference_exam = train(), assess()
        d.h.require(reference[0].goal_id == rows[0]['id']
                    and len(reference_exam) == 2, 'reference lowering mismatch')
        counts = install_scope()
        for _ in range(2):
            d.h.require(train() == reference, 'prepared training goals drift')
            d.h.require(assess() == reference_exam, 'prepared evaluation instruments drift')
        for key in ('operator_registry_hit', 'operator_digest_hit',
                    'source_registry_hit', 'lowerers_hit'):
            d.h.require(counts[key] > 0, 'unexercised reuse: ' + key)
        saved = dict(counts)
        # Semantic-release changes must produce an independently lowered goal.
        alternate_release = 'b' * 64
        alternate = SimpleNamespace(sources=compiled.sources,
            compiled=SimpleNamespace(features=SimpleNamespace(semantic_release=alternate_release)))
        changed = training._learning_first_task_goals(context, alternate)
        d.h.require(changed[0].semantic_release == alternate_release
                    and changed[1].semantic_release == alternate_release
                    and changed != reference, 'semantic release was not isolated')
        d.h.require(counts['operator_registry_miss'] == saved['operator_registry_miss'] + 1,
                    'semantic release change did not invalidate')
        saved = dict(counts)
        # A new admitted source context, even with equal semantic contents,
        # must not consume an older owner's prepared registries.
        _, new_context, _, _ = _execution_context(run)
        if new_context is context:
            from dataclasses import replace
            new_context = replace(context)
            object.__setattr__(new_context, '_accepted_feature_context', feature)
        d.h.require(new_context is not context, 'new source owner unavailable')
        d.h.require(training._learning_first_task_goals(new_context, compiled)
                    == reference, 'new owner changed lowering')
        d.h.require(counts['owner_scopes'] == saved['owner_scopes'] + 1
                    and counts['operator_registry_miss'] == saved['operator_registry_miss'] + 1,
                    'source owner change did not invalidate')
        saved = dict(counts)
    with evidence_mode(strict=True):
        d.h.require(train() == reference, 'strict lowering drift')
        d.h.require(dict(counts) == saved, 'strict path consumed prepared state')
    print('SCOPE_SMOKE_PASS', json.dumps(saved, sort_keys=True), flush=True)
