"""Governed, non-destructive semantic-ledger revision and pinned-model reconciliation.

A spreadsheet is a living *view*, not the neural model's mutable runtime ABI.
Model learning retains its pinned semantic contract while edits are reviewed.
No function here alters checkpoint weights, AdamW, old token IDs or live Sheets.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Mapping

from .token_atlas import COLUMNS, rows_for_graph
from .vocabulary_growth import digest

SCHEMA = 'bilqis.mlx.registry-semantic-revisions/v1'
# Immutable ABI columns, distinct from editorial/source-provenance fields.
IDENTITY_COLS = (0, 1, 2, 4, 5, 6, 7, 8, 9, 10)
EDITORIAL_COLS = (3, 11, 12, 13, 14, 15)
REVIEW_COLUMNS = (
    'Revision ID', 'Parent version', 'Token ID', 'Token symbol',
    'Legacy pasigraphy identity', 'Previous recorded description',
    'Proposed description', 'Proposed New Ithkuil bridge',
    'Relation / change type', 'Source URL', 'Primary source location',
    'Evidence / distinction', 'Disposition', 'Approval authority',
    'Approval reference', 'Applied in ledger version',
)
CHANGE_KINDS = frozenset(('EDITORIAL_ANNOTATION', 'COMPATIBLE_EQUIVALENCE',
                         'PARTIAL_OR_RELATED', 'MEANING_CHANGE_REQUIRES_RETEACH'))


@dataclass(frozen=True)
class ProposedRevision:
    revision_id: str
    parent_version: str
    token_id: int
    token_symbol: str
    legacy_identity: str
    old_description: str
    proposed_description: str
    proposed_bridge: str
    change_kind: str
    primary_url: str
    primary_locus: str
    reasoning: str
    disposition: str = 'PROPOSED_REVIEW'
    approval_authority: str = ''
    approval_reference: str = ''
    applied_version: str = ''


def revision_row(p: ProposedRevision) -> list[str]:
    return [p.revision_id,p.parent_version,str(p.token_id),p.token_symbol,
            p.legacy_identity,p.old_description,p.proposed_description,
            p.proposed_bridge,p.change_kind,p.primary_url,p.primary_locus,
            p.reasoning,p.disposition,p.approval_authority,
            p.approval_reference,p.applied_version]


def _validate_rows(expected: list[list[str]], observed: list[list[object]]) -> list[list[str]]:
    if not isinstance(observed,list) or not observed:
        raise ValueError('REGISTRY_SNAPSHOT_EMPTY')
    header = tuple(str(x) for x in observed[0])
    if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
        raise ValueError('REGISTRY_HEADER_INCOMPATIBLE')
    rows=[[str(x) for x in r] for r in observed[1:]]
    if any(len(r)!=len(COLUMNS) for r in rows):
        raise ValueError('REGISTRY_SHEET_MALFORMED')
    order = tuple(header.index(name) for name in COLUMNS)
    return [[row[index] for index in order] for row in rows]


def reconcile_live_ledger(graph: dict, live_sheet_rows: list[list[object]], *,
                          pinned_version: str, approved_annotations: Mapping[str,Mapping[int,str]]|None=None) -> dict:
    """Report drift against a pinned semantic version, never invalidate the model.

    Historic embedded graph is the source of model-token identity. Approved
    annotations are a *versioned sidecar* not a rewriting of that graph.
    """
    if not pinned_version:
        raise ValueError('REGISTRY_PINNED_VERSION_REQUIRED')
    expected=rows_for_graph(graph)
    live=_validate_rows(expected,live_sheet_rows)
    if len(live)!=len(expected):
        return {'schema':SCHEMA,'pinned_version':pinned_version,
                'disposition':'CONTINUE_PINNED_MODEL_HOLD_NEW_ALLOCATIONS',
                'missing_or_extra_rows':abs(len(live)-len(expected)),
                'identity_conflicts':True,'pending_reviews':(),
                'can_promote_new_semantic_version':False,
                'neural_checkpoint_invalidated':False}
    approved_annotations=approved_annotations or {}
    conflicts=[];pending=[]
    for index,(reference,actual) in enumerate(zip(expected,live)):
        if any(actual[column]!=reference[column] for column in IDENTITY_COLS):
            conflicts.append(index)
        for column in EDITORIAL_COLS:
            approved=approved_annotations.get(str(index),{}).get(column,reference[column])
            if actual[column]!=approved:
                pending.append({'token_id':index,'column':COLUMNS[column],
                                'approved_value':approved,'proposed_value':actual})
    return {'schema':SCHEMA,'pinned_version':pinned_version,
            'disposition':('CONTINUE_PINNED_MODEL_HOLD_NEW_ALLOCATIONS'
                           if conflicts else 'CONTINUE_PINNED_MODEL'),
            'identity_conflicts':bool(conflicts),
            'conflict_token_ids':tuple(conflicts),
            'pending_reviews':tuple(pending),
            'can_promote_new_semantic_version':not conflicts and not pending,
            'neural_checkpoint_invalidated':False,
            'identity_token_count':len(expected)}


def review_proposal(proposal: ProposedRevision, *, pinned_version: str,
                    graph: dict) -> dict:
    """Stage an authentic proposal; no app-level approval is invented."""
    rows=rows_for_graph(graph)
    if (not isinstance(proposal,ProposedRevision) or
            proposal.parent_version != pinned_version or
            not proposal.revision_id.strip() or
            proposal.token_id<0 or proposal.token_id>=len(rows) or
            proposal.token_symbol!=rows[proposal.token_id][1] or
            proposal.legacy_identity!=rows[proposal.token_id][2] or
            proposal.old_description!=rows[proposal.token_id][3] or
            proposal.change_kind not in CHANGE_KINDS or
            proposal.disposition!='PROPOSED_REVIEW' or
            proposal.approval_authority or proposal.approval_reference or
            proposal.applied_version or not proposal.primary_url.startswith('https://') or
            not proposal.primary_locus.strip() or not proposal.reasoning.strip()):
        raise ValueError('REGISTRY_PROPOSAL_NOT_TRACEABLE_OR_PREAPPROVED')
    return {'schema':SCHEMA,'revision_id':proposal.revision_id,
            'digest':digest(revision_row(proposal)),
            'disposition':'PENDING_HUMAN_REVIEW',
            'model_version_unchanged':pinned_version,'neural_updates':0}


def approved_revision(proposal: ProposedRevision, *, reviewer: str,
                      authority_reference: str, next_version: str,
                      verified_authority_digest: str) -> dict:
    """Represent externally verified approval, never grant it to a caller.

    The external caller must read/verify the actual human approval and supply
    its source-content digest. Source truth cannot be proven from a bare string.
    """
    if proposal.disposition!='PROPOSED_REVIEW':
        raise ValueError('REGISTRY_PROPOSAL_NOT_PENDING')
    if (not reviewer.strip() or
            not authority_reference.startswith('https://') or
            not next_version.strip() or next_version==proposal.parent_version or
            not isinstance(verified_authority_digest,str) or
            len(verified_authority_digest)!=64 or
            any(c not in '0123456789abcdef' for c in verified_authority_digest)):
        raise ValueError('REGISTRY_EXTERNAL_APPROVAL_EVIDENCE_REQUIRED')
    if proposal.change_kind=='MEANING_CHANGE_REQUIRES_RETEACH':
        return {'schema':SCHEMA,'disposition':'APPROVED_NEW_INSTRUCTION_REQUIRED',
                'pinned_model_version':proposal.parent_version,
                'proposed_model_version':next_version,
                'previous_neural_competence_preserved':True,
                'neural_updates':0,
                'authority_receipt':verified_authority_digest}
    return {'schema':SCHEMA,'disposition':'APPROVED_COMPATIBLE_ANNOTATION',
            'pinned_model_version':proposal.parent_version,
            'new_ledger_version':next_version,
            'revision_digest':digest(revision_row(proposal)),
            'authority_receipt':verified_authority_digest,
            'old_neural_checkpoint_still_valid':True,
            'neural_updates':0}


def materialize_approved_mapping(graph: dict, base_rows: list[list[str]],
                                 proposal: ProposedRevision,
                                 approval: dict) -> tuple[list[list[str]], dict]:
    """Derive a new, non-destructive ledger view, not a mutation of old evidence.

    A substantive change in token meaning may require new teaching and must
    not be normalized into an alias over the old neural representation.
    """
    if (approval.get('disposition')!='APPROVED_COMPATIBLE_ANNOTATION' or
            approval.get('revision_digest')!=digest(revision_row(proposal)) or
            approval.get('pinned_model_version')!=proposal.parent_version):
        raise ValueError('REGISTRY_MAPPING_HAS_NO_COMPATIBLE_APPROVAL')
    expected=rows_for_graph(graph)
    if ([str(x) for x in base_rows[0]]!=list(COLUMNS) or
            len(base_rows)!=len(expected)+1 or
            any(len(actual)!=len(COLUMNS) or
                any(str(actual[c])!=reference[c] for c in IDENTITY_COLS)
                for actual,reference in zip(base_rows[1:],expected))):
        raise ValueError('REGISTRY_PARENT_LEDGER_IDENTITY_DRIFT')
    if proposal.change_kind=='MEANING_CHANGE_REQUIRES_RETEACH':
        raise ValueError('REGISTRY_MEANING_REQUIRES_NEW_STUDENT_INSTRUCTION')
    view=copy.deepcopy(base_rows)
    row=view[proposal.token_id+1]
    if row[1]!=proposal.token_symbol or row[2]!=proposal.legacy_identity:
        raise ValueError('REGISTRY_APPROVED_TOKEN_IDENTITY_MISMATCH')
    row[11]=proposal.proposed_bridge
    row[14]='NI_REVIEWED_MAPPING_NOT_MASTERY'
    row[15]='revision:'+proposal.revision_id+' | '+proposal.primary_url
    # Legacy role remains intact; human-reviewed commentary is an annotation.
    return view, {'schema':SCHEMA,'from_version':proposal.parent_version,
                  'to_version':approval['new_ledger_version'],
                  'revision':proposal.revision_id,
                  'source_graph_unmodified':True,'student_checkpoint_unmodified':True,
                  'old_semantic_identity_preserved':True,
                  'changed_columns':(11,14,15),'neural_updates':0}
