"""Append-only semantic-token allocation for a future MLX Bilqis student.

A research seed is never an admitted model token. Semantic admission, neural
allocation, instruction, testing and mastery are separate events. This module
implements an in-memory, neural-inert allocation transition, not a curriculum
or authority to run optimizer updates on the historic whole student.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import hashlib
import json
import re
from typing import Mapping

SCHEMA = "bilqis.mlx.semantic-vocabulary-growth/v1"
SOURCE_KINDS = frozenset(("new_ithkuil", "mathematics", "logic", "lexicalized", "other_domain"))
REPRESENTATIONS = frozenset(("atomic", "compositional", "hybrid"))
GROWTH_STATE = "LEARNING_ADMITTED_NOT_YET_MASTERED"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",", ":"),
                                     ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _sha(value: str) -> bool:
    return isinstance(value,str) and bool(re.fullmatch(r"[0-9a-f]{64}",value))


@dataclass(frozen=True)
class ResearchSeed:
    """A candidate meaning, not necessarily an independent neural token."""
    candidate_id: str
    gloss: str
    provenance: str
    source_kind: str
    suggested_representation: str
    rationale: str
    state: str = "RESEARCH_SEED_NOT_TAUGHT"


@dataclass(frozen=True)
class AdmittedToken:
    """External prerequisite/oracle admission receipts are required before allocation.

    Even an admitted token is *unmastered*. A higher-level course authority
    independently verifies the source, teaching and assessment receipts.
    """
    token_id: str
    semantic_id: str
    meaning: str
    source_kind: str
    representation: str
    source_locator: str
    source_digest: str
    lesson_digest: str
    oracle_digest: str
    prerequisite_tokens: tuple[str,...]
    capability_id: str
    admission_receipt: str
    state: str = GROWTH_STATE
    signature: str = "SemanticSymbol"
    arity: int = 0


def candidate_examples() -> tuple[ResearchSeed,...]:
    """User-supplied lexicalized examples only; no invented NI etymology."""
    return (
        ResearchSeed("LEX-ENSHITTIFICATION", "enshittification", "user:2026-10-15",
                     "lexicalized", "atomic", "Lexicalized mechanism may exceed a convenient NI-root paraphrase"),
        ResearchSeed("LEX-SHIBBOLETH", "shibboleth", "user:2026-10-15",
                     "lexicalized", "atomic", "Distinct social boundary-marking meaning may need its own root"),
    )


def _check_catalog(catalog: dict) -> None:
    if not isinstance(catalog,dict) or not {'tokens','nodes','row_contract_sha256'} <= set(catalog):
        raise ValueError("VOCAB_CATALOG_MISSING_FIELDS")
    tokens=catalog['tokens'];nodes=catalog['nodes'];receipts=catalog['row_contract_sha256']
    if (not isinstance(tokens,list) or not tokens or
            not isinstance(nodes,list) or len(nodes)!=len(tokens) or
            any(not isinstance(x,str) or not x for x in tokens) or
            len(tokens)!=len(set(tokens)) or
            [n.get('id') for n in nodes]!=tokens or
            not isinstance(receipts,dict) or set(receipts)!=set(tokens)):
        raise ValueError("VOCAB_CATALOG_IDENTITY_DRIFT")
    for node in nodes:
        if receipts[node['id']] != digest(node):
            raise ValueError("VOCAB_CATALOG_EXISTING_ROW_CHANGED")
    provenance = catalog.get('allocation_source_graph_sha256', {})
    if (not isinstance(provenance, dict) or not set(provenance) <= set(tokens) or
            any(not _sha(value) for value in provenance.values())):
        raise ValueError('VOCAB_ALLOCATION_PROVENANCE_INVALID')


def _check_admission(entry: AdmittedToken, prior: set[str], additional: set[str]):
    if (not isinstance(entry,AdmittedToken) or entry.state != GROWTH_STATE or
            not re.fullmatch(r"[a-z][A-Za-z0-9._-]{2,120}",entry.token_id) or
            not entry.semantic_id or not entry.meaning.strip() or
            entry.source_kind not in SOURCE_KINDS or
            entry.representation not in REPRESENTATIONS or
            not entry.source_locator.strip() or not entry.capability_id.strip() or
            any(not _sha(x) for x in (entry.source_digest,entry.lesson_digest,
                                       entry.oracle_digest,entry.admission_receipt))):
        raise ValueError("VOCAB_ROOT_HAS_NO_ATTESTED_ADMISSION_OR_BAD_IDENTITY")
    if type(entry.arity) is not int or entry.arity < 0:
        raise ValueError("VOCAB_TYPED_ARITY_INVALID")
    if entry.arity:
        from .semantics.core import Signature
        signature = Signature.parse(entry.signature)
        if len(signature.inputs) != entry.arity:
            raise ValueError("VOCAB_TYPED_SIGNATURE_ARITY_MISMATCH")
    elif not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", entry.signature):
        raise ValueError("VOCAB_LITERAL_TYPE_INVALID")
    if not isinstance(entry.prerequisite_tokens,tuple):
        raise ValueError("VOCAB_PREREQUISITE_TYPE")
    if any(p not in prior|additional for p in entry.prerequisite_tokens):
        raise ValueError("VOCAB_ROOT_HAS_UNTAUGHT_PREREQUISITE_ID")


def append_catalog(prior: dict, admissions: tuple[AdmittedToken,...], *,
                   allow_disposable_fixtures: bool = False,
                   canonical_registry_rows: list[list[object]] | None = None,
                   approved_ledger_version: str = '',
                   approved_admissions: tuple[str,...] = ()) -> tuple[dict,dict]:
    """Extend graph identities without changing one byte of old row JSON."""
    _check_catalog(prior)
    if not isinstance(admissions,tuple) or not admissions:
        raise ValueError("VOCAB_ADMISSIONS_REQUIRED_NOT_RESEARCH_SEEDS")
    prior_ids=set(prior['tokens'])
    seen=set()
    prior_concepts={node.get('semantic_id') or ('legacy:'+node['id'])
                    for node in prior['nodes']}
    seen_concepts=set()
    nodes=[]
    for entry in admissions:
        _check_admission(entry,prior_ids,seen)
        if entry.semantic_id in prior_concepts|seen_concepts:
            raise ValueError('PASIGRAPHY_SEMANTIC_IDENTITY_ALREADY_ASSIGNED')
        if (not allow_disposable_fixtures and
                (entry.token_id.startswith('fixture.') or
                 entry.semantic_id.startswith('fixture:') or
                 entry.source_locator.startswith(('fixture:', 'test:')))):
            raise ValueError('VOCAB_DISPOSABLE_FIXTURE_CANNOT_ENTER_REAL_CATALOG')
        if entry.token_id in prior_ids|seen:
            raise ValueError("VOCAB_EXISTING_OR_DUPLICATE_TOKEN_ID")
        seen.add(entry.token_id)
        seen_concepts.add(entry.semantic_id)
        nodes.append({
            'id':entry.token_id, 'family':entry.source_kind,
            'subtype':entry.representation, 'signature':entry.signature,
            'arity':entry.arity,'stage':0,
            'source':entry.source_locator,
            'semantic_id':entry.semantic_id,
            'meaning':entry.meaning,
            'capability_id':entry.capability_id,
            'admission_receipt':entry.admission_receipt,
            'state':GROWTH_STATE,
            'edges':[{'kind':'prerequisite','target':p} for p in entry.prerequisite_tokens],
        })
    result=copy.deepcopy(prior)
    # After the first allocation, native rows retain their allocation epoch's
    # source graph. Storing only *prior* hashes avoids a self-referential digest.
    if any('semantic_id' in node for node in prior['nodes']):
        from .token_atlas import rows_for_graph
        result['allocation_source_graph_sha256'] = {
            row[1]: row[10] for row in rows_for_graph(prior)}
    result['tokens'].extend([entry.token_id for entry in admissions])
    result['nodes'].extend(nodes)
    result['row_contract_sha256'].update({n['id']:digest(n) for n in nodes})
    _check_catalog(result)
    from .token_atlas import validate_one_to_one
    validate_one_to_one(result)
    if not allow_disposable_fixtures:
        if canonical_registry_rows is None:
            raise ValueError('PASIGRAPHY_CANONICAL_REGISTRY_READBACK_REQUIRED')
        from .registry_versions import reconcile_live_ledger
        view=reconcile_live_ledger(result,canonical_registry_rows,
                                  pinned_version=approved_ledger_version or 'legacy-source/v1')
        if view['identity_conflicts']:
            raise ValueError('PASIGRAPHY_NEW_ADMISSION_IDENTITY_CONFLICT')
        # A living ledger may receive editorial proposals without rewriting
        # the existing student. New allocations still need *their own*
        # approved admission receipts in the pinned control version.
        if (set(approved_admissions)!={a.admission_receipt for a in admissions}
                or not approved_ledger_version):
            raise ValueError('PASIGRAPHY_NEW_ADMISSION_APPROVAL_REQUIRED')
    if result['tokens'][:len(prior['tokens'])]!=prior['tokens'] or \
            result['nodes'][:len(prior['nodes'])]!=prior['nodes'] or \
            any(result['row_contract_sha256'][p]!=prior['row_contract_sha256'][p]
                for p in prior['tokens']):
        raise ValueError("VOCAB_GROWTH_CHANGED_EXISTING_SEMANTICS")
    receipt={'schema':SCHEMA,'parent_graph_digest':digest(prior),
             'expanded_graph_digest':digest(result),
             'old_token_count':len(prior['tokens']),
             'added_token_count':len(admissions),
             'new_token_count':len(result['tokens']),
             'new_token_ids':[e.token_id for e in admissions],
             'admission_receipts':[e.admission_receipt for e in admissions],
             'legacy_prefix_preserved':True,
             'neural_updates':0,'new_semantics_mastered':False}
    return result,receipt


def _new_embedding_row(identity: str, node_digest: str, width: int):
    """Deterministic small seed; no claim of learned linguistic meaning."""
    import numpy as np
    vector=np.empty(width,dtype=np.float32)
    for column in range(width):
        h=hashlib.sha256(f'{SCHEMA}|{identity}|{node_digest}|{column}'.encode()).digest()
        vector[column]=1.0 if h[0]&1 else -1.0
    vector *= np.float32(0.02)
    return vector


def extend_mlx_student(parameters: Mapping[str,object], optimizer,
                       prior_catalog: dict, expanded_catalog: dict):
    """Allocate new embedding rows and zero AdamW moments in a *new* state.

    No optimizer.update(), no change to the source optimizer, no disk writes.
    Full model forward on existing input/output token IDs is invariant.
    """
    import mlx.core as mx
    import mlx.optimizers as optim
    import numpy as np
    _check_catalog(prior_catalog)
    _check_catalog(expanded_catalog)
    n=len(prior_catalog['tokens']); total=len(expanded_catalog['tokens'])
    if total<=n or expanded_catalog['tokens'][:n]!=prior_catalog['tokens'] or \
           expanded_catalog['nodes'][:n]!=prior_catalog['nodes'] or \
           any(expanded_catalog['row_contract_sha256'][p]!=prior_catalog['row_contract_sha256'][p]
               for p in prior_catalog['tokens']):
        raise ValueError("MLX_VOCAB_GROWTH_NOT_STRICTLY_APPEND_ONLY")
    if 'embedding.weight' not in parameters:
        raise ValueError("MLX_VOCAB_MISSING_TIED_EMBEDDING")
    original=parameters['embedding.weight']
    if not isinstance(original,mx.array) or original.dtype!=mx.float32 or \
           original.ndim!=2 or original.shape[0]!=n:
        raise ValueError("MLX_VOCAB_MODEL_GRAPH_SIZE_DRIFT")
    if not optimizer.bias_correction:
        raise ValueError("MLX_VOCAB_UNEXPECTED_ADAMW_MODE")
    state=optimizer.state
    if set(state)!={'step','learning_rate',*parameters}:
        raise ValueError("MLX_VOCAB_INCOMPLETE_OPTIMIZER_STATE")
    for name,weight in parameters.items():
        if not isinstance(weight,mx.array) or weight.dtype!=mx.float32 or \
               set(state[name])!={'m','v'} or any(state[name][slot].shape!=weight.shape
                                                for slot in ('m','v')):
            raise ValueError("MLX_VOCAB_UNVERIFIED_PARAMETER_MOMENTS")
    width=int(original.shape[1])
    rows=np.stack([_new_embedding_row(token,expanded_catalog['row_contract_sha256'][token],width)
                   for token in expanded_catalog['tokens'][n:]])
    extended=mx.concatenate((original,mx.array(rows)),axis=0)
    new_params=dict(parameters)
    new_params['embedding.weight']=extended
    copied={'step':mx.array(state['step']),
            'learning_rate':mx.array(state['learning_rate'])}
    for key in parameters:
        old=state[key]
        if key=='embedding.weight':
            copied[key]={kind:mx.concatenate((mx.array(old[kind]),
                     mx.zeros((total-n,width),dtype=mx.float32)),axis=0)
                     for kind in ('m','v')}
        else:
            copied[key]={kind:mx.array(old[kind]) for kind in ('m','v')}
    new_opt=optim.AdamW(learning_rate=float(copied['learning_rate'].item()),
                       betas=list(optimizer.betas),eps=float(optimizer.eps),
                       weight_decay=float(optimizer.weight_decay),
                       bias_correction=True)
    new_opt.state=copied
    mx.eval(new_params,new_opt.state)
    if (not np.array_equal(np.asarray(original),np.asarray(extended[:n])) or
            any(not np.array_equal(np.asarray(state['embedding.weight'][part]),
                                   np.asarray(copied['embedding.weight'][part][:n]))
                for part in ('m','v')) or
            any(np.count_nonzero(np.asarray(copied['embedding.weight'][part][n:]))
                for part in ('m','v')) or
            int(new_opt.state['step'].item())!=int(state['step'].item())):
        raise ValueError("MLX_VOCAB_GROWTH_MUTATED_PREVIOUS_STUDENT")
    receipt={'schema':SCHEMA,'old_vocab':n,'new_vocab':total,
             'added_rows':total-n,'embedding_width':width,
             'estimated_new_fp32_weight_and_adamw_bytes':(total-n)*width*4*3,
             'old_weight_rows_preserved_exactly':True,
             'old_moments_preserved_exactly':True,
             'new_moments_zero':True,
             'adamw_step':int(state['step'].item()),
             'old_optimizer_unchanged':True,'train_updates':0,
             'new_semantics_mastered':False,
             'read_only_parent_lineage':True}
    return new_params,new_opt,receipt
