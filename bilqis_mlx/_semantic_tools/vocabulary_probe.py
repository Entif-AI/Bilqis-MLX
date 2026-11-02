"""Read-only in-memory vocabulary expansion of the *real* historic student.

Creates one fixture-only prospective token in RAM, checks old logits and
AdamW identities and exits. No changed checkpoint is written and no neural
optimizer updates are made. Never confuse a fixture allocation with a root
curriculum admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .backup import digest_file
from bilqis_mlx.runtime.mlx_parity import forward, native_optimizer_to_mlx
from .source import AUDITED_PARENT
from .semantics.abi import HISTORICAL_PREFIX_SIZE
from .vocabulary_growth import AdmittedToken, append_catalog, extend_mlx_student


def probe(checkpoint: Path, legacy_root: Path) -> dict:
    import mlx.core as mx
    import numpy as np
    import torch

    root=Path(legacy_root).resolve(strict=True)
    source=(root/'bilqis_development/continuation.py').resolve(strict=True)
    sys.path.insert(0,str(root))
    sys.dont_write_bytecode=True
    from bilqis_development.continuation import load
    if Path(sys.modules[load.__module__].__file__).resolve()!=source:
        raise ValueError('VOCAB_PREFLIGHT_WRONG_HISTORIC_SOURCE_LOADER')
    checkpoint=Path(checkpoint).resolve(strict=True)
    if digest_file(checkpoint)!=AUDITED_PARENT.sha256:
        raise ValueError('VOCAB_PREFLIGHT_CHECKPOINT_SHA_DRIFT')
    mx.set_default_device(mx.cpu)
    model,optimizer,payload=load(checkpoint)
    model.eval()
    cfg=payload['config'];catalog=payload['graph']
    if (cfg['precision']!='fp32' or cfg['vocab_size']!=HISTORICAL_PREFIX_SIZE or
            len(catalog['tokens'])!=HISTORICAL_PREFIX_SIZE or
            payload.get('optimizer_receipt',{}).get('steps')!=[116760]):
        # Optimizer receipt structure may vary; fail if this implementation's
        # graph/model/checkpoint is not the exact audited historical parent.
        raise ValueError('VOCAB_PREFLIGHT_HISTORIC_PARENT_SHAPE_DRIFT')
    params={name:mx.array(value.detach().cpu().numpy(),dtype=mx.float32)
            for name,value in model.state_dict().items()}
    name_by_object={id(p):name for name,p in model.named_parameters()}
    order=tuple(name_by_object[id(p)] for p in optimizer.param_groups[0]['params'])
    info,mlopt=native_optimizer_to_mlx(optimizer.state_dict(),model.state_dict(),
                                      parameter_order=order)
    answer_ids=model.answer_ids.cpu().numpy().tolist()
    ids=np.array([[4,6,7,0],[6,7,8,9]],dtype=np.int32)
    lengths=np.array([3,4],dtype=np.int32)
    before=forward(mx,params,ids,lengths,heads=cfg['heads'],layers=cfg['layers'],
                   answer_ids=answer_ids)
    toy_hash=lambda label:hashlib.sha256(('DISPOSABLE_NOT_REAL:'+label).encode()).hexdigest()
    fixture=AdmittedToken(
        token_id='fixture.untrained.test-token',semantic_id='fixture:untrained',
        meaning='Disposable vocabulary expansion verification, not a real lexical root',
        source_kind='other_domain',representation='atomic',
        source_locator='test:disposable-read-only',source_digest=toy_hash('source'),
        lesson_digest=toy_hash('lesson'),oracle_digest=toy_hash('oracle'),
        prerequisite_tokens=(),capability_id='fixture.only',admission_receipt=toy_hash('receipt'))
    new_graph,plan=append_catalog(catalog,(fixture,),allow_disposable_fixtures=True)
    grown,grown_opt,receipt=extend_mlx_student(params,mlopt,catalog,new_graph)
    after=forward(mx,grown,ids,lengths,heads=cfg['heads'],layers=cfg['layers'],
                  answer_ids=answer_ids)
    if not np.array_equal(before,after):
        raise ValueError('VOCAB_OLD_STUDENT_LOGITS_CHANGED_AFTER_APPEND')
    old_token_ids={tok:i for i,tok in enumerate(catalog['tokens'])}
    if any(new_graph['tokens'][i]!=s for s,i in old_token_ids.items()):
        raise ValueError('VOCAB_OLD_TOKEN_ID_CHANGED')
    if digest_file(checkpoint)!=AUDITED_PARENT.sha256:
        raise ValueError('VOCAB_HISTORIC_CHECKPOINT_CHANGED_DURING_PREFLIGHT')
    return {'schema':'bilqis.mlx.real-student-read-only-growth-probe/v1',
            'state':'READ_ONLY_PARENT_PRESERVED_NO_NEW_SEMANTIC_MASTERY',
            'checkpoint_sha256':AUDITED_PARENT.sha256,
            'original_model_token_count':len(catalog['tokens']),
            'in_memory_fixture_extended_count':len(new_graph['tokens']),
            'old_token_ids_unchanged':True,
            'old_logits_exactly_unchanged':True,
            'max_old_logit_abs_diff':float(np.max(np.abs(before-after))),
            'old_embedding_rows_exactly_unchanged':receipt['old_weight_rows_preserved_exactly'],
            'old_adamw_moments_exactly_unchanged':receipt['old_moments_preserved_exactly'],
            'adamw_step_unchanged':receipt['adamw_step']==info['native_step'],
            'appended_moment_rows_zero':receipt['new_moments_zero'],
            'fixture_only_new_root_id':fixture.token_id,
            'new_roots_trained':0,'neural_optimizer_updates':0,
            'checkpoint_saved':False,'historic_checkpoint_unchanged':True,
            'source_graph_digest':plan['parent_graph_digest'],
            'fixture_graph_digest':plan['expanded_graph_digest']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',required=True,type=Path)
    p.add_argument('--legacy-code-root',required=True,type=Path)
    args=p.parse_args(argv)
    print(json.dumps(probe(args.checkpoint,args.legacy_code_root),sort_keys=True,indent=2))


if __name__=='__main__':
    main()
