"""Read-only completion latch for versioned School50 curricula.

Never infer completion from historical G exams, best-ever champion scores,
or measurements taken at different optimizer steps. A future trainer must
persist the complete measured-current-program receipt at a grade boundary,
then call completion_status before scheduling another grade.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA='bilqis.school50.current-completion/v1'
V15='bilqis.primitive-consolidation.run-local/v15'


def completion_status(state):
    """Return (complete, reason). Invalid or absent metrics never pass."""
    config=state.get('config') or {}
    requirements=config.get('current_assessment_metrics')
    if state.get('version')==V15:
        from .graduation_inventory_v15 import approved_inventory
        try:
            rubric=approved_inventory(config.get('grade_program') or ())
        except ValueError as error:
            return False,str(error)
        requirements={key:entry['total'] for key,entry in rubric.items()}
        if (config.get('current_assessment_metrics') is not None and
                config['current_assessment_metrics']!=requirements):
            return False,'INVALID_CURRENT_METRIC_INVENTORY'
    if not isinstance(requirements,dict) or not requirements:
        return False,'NO_APPROVED_CURRENT_METRIC_INVENTORY'
    if any(not isinstance(key,str) or not key or
           type(total) is not int or total<=0
           for key,total in requirements.items()):
        return False,'INVALID_CURRENT_METRIC_INVENTORY'
    receipt=state.get('mastery_completion')
    if not isinstance(receipt,dict):
        return False,'NO_SAME_CHECKPOINT_MASTERY_RECEIPT'
    if (receipt.get('schema')!=SCHEMA or
            receipt.get('training_version')!=state.get('version') or
            receipt.get('optimizer_step')!=state.get('optimizer_step') or
            receipt.get('checkpoint')!=state.get('checkpoint') or
            receipt.get('checkpoint_sha256')!=state.get('checkpoint_sha256')):
        return False,'STALE_OR_UNVERIFIED_MASTERY_RECEIPT'
    if state.get('version')==V15:
        from bilqis_logic.kernel import digest
        if receipt.get('current_rubric_sha256')!=digest(rubric):
            return False,'STALE_OR_UNVERIFIED_MASTERY_RECEIPT'
    observed=receipt.get('metrics')
    if not isinstance(observed,dict) or set(observed)!=set(requirements):
        return False,'INCOMPLETE_CURRENT_METRIC_COVERAGE'
    for key,total in requirements.items():
        row=observed[key]
        if (not isinstance(row,dict) or
                type(row.get('correct')) is not int or
                type(row.get('total')) is not int or
                row['total']!=total or
                not 0<=row['correct']<=total or
                row.get('optimizer_step')!=state['optimizer_step'] or
                row.get('checkpoint_sha256')!=state['checkpoint_sha256']):
            return False,'INVALID_OR_MIXED_CHECKPOINT_SCORE:'+key
        if row['correct']!=total:
            return False,'UNMASTERED_CURRENT_METRIC:'+key
    return True,'ALL_CURRENT_METRICS_100_PERCENT'


def verify_complete_checkpoint(run_dir,state):
    """Validate the actual native full model+own AdamW before dashboard latch."""
    if state.get('version')!=V15:
        return True,'NON_V15_LEGACY_COMPLETION'
    from . import time_first_runner_v15 as trainer
    from bilqis_logic.kernel import digest
    from bilqis_ref.model import state_hash
    try:
        model,_optimizer,graph=trainer._load_student(Path(run_dir),state,'cpu')
        receipt=state['mastery_completion']
        if (receipt.get('model_sha256')!=state_hash(model) or
                receipt.get('graph_sha256')!=digest(graph)):
            return False,'STALE_OR_UNVERIFIED_FULL_CHECKPOINT_RECEIPT'
    except Exception as error:
        return False,'INVALID_FULL_FP32_ADAMW_CHECKPOINT:'+type(error).__name__
    return True,'VERIFIED_FULL_FP32_ADAMW_CHECKPOINT'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    args=parser.parse_args()
    try:
        source=args.run_dir/'state.json'
        state=json.loads(source.read_text(encoding='utf-8'))
    except FileNotFoundError:
        print('NOT_STARTED; no completion receipt')
        return 1
    except (OSError,ValueError,TypeError) as error:
        print(f'INVALID_COMPLETION_STATE: {error}')
        return 2
    complete,reason=completion_status(state)
    print(reason)
    if complete:
        verified,proof=verify_complete_checkpoint(args.run_dir,state)
        print(proof)
        return 0 if verified else 2
    # Missing completion evidence is an ordinary incomplete curriculum.
    # Contradictory completion evidence is unsafe to bypass implicitly.
    if reason.startswith(('INVALID_', 'STALE_', 'INCOMPLETE_')):
        return 2
    return 1


if __name__=='__main__':
    raise SystemExit(main())
