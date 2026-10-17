"""Versioned semantic graph and typed composition AST, without model weights.

The graph owns source-grounded identities and allowed composition signatures.
The AST composes those identities; it does not reduce a New Ithkuil lexeme to
an English word or claim to implement a surface grammar. No learning occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias

SCHEMA = 'bilqis.semantic-spine/v0.1.0'
SEED = Path(__file__).with_name('seed.json')
KINDS = frozenset({'SEMANTIC_FACTOR','ROOT','STEM','SPECIFICATION','MANIFESTATION',
                   'GRAMMATICAL_CATEGORY','SLOT','COMPETENCY'})
ADMISSION = frozenset({'SOURCE_ATTESTED','AUTHOR_DESIGN'})
RELATIONS = MappingProxyType({
    'ROOT_HAS_FACTOR': ('ROOT','SEMANTIC_FACTOR'),
    'STEM_HAS_FACTOR': ('STEM','SEMANTIC_FACTOR'),
    'FACTOR_HAS_FACTOR': ('SEMANTIC_FACTOR','SEMANTIC_FACTOR'),
    'HAS_STEM': ('ROOT','STEM'),
    'OCCUPIES_SLOT': ('ROOT','SLOT'),
    'STEM_MARKED_IN_SLOT': ('STEM','SLOT'),
    'SPEC_MARKED_IN_SLOT': ('SPECIFICATION','SLOT'),
    'CATEGORY_MARKED_IN_SLOT': ('GRAMMATICAL_CATEGORY','SLOT'),
    'UPGRADES': ('COMPETENCY','COMPETENCY'),
})


def _exact(value, keys, label):
    if not isinstance(value,dict) or set(value)!=set(keys):
        raise ValueError(f'SPINE_INVALID_{label}_FIELDS')


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),
                      ensure_ascii=True,allow_nan=False)


@dataclass(frozen=True)
class Source:
    id: str
    edition: str
    url: str
    section: str
    basis: str


@dataclass(frozen=True)
class Concept:
    id: str
    kind: str
    name: str
    source: str
    admission: str
    ordinal: int | None
    tier: int
    note: str


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str
    authority: str


@dataclass(frozen=True)
class Signature:
    id: str
    inputs: tuple[str,...]
    output: str
    source: str


@dataclass(frozen=True)
class Atom:
    concept_id: str


@dataclass(frozen=True)
class Apply:
    operator: str
    args: tuple['Expression',...]


Expression: TypeAlias = Atom | Apply


class SemanticGraph:
    def __init__(self,manifest: dict):
        _exact(manifest,('schema','sources','concepts','edges','operators'),
               'MANIFEST')
        if manifest['schema']!=SCHEMA:
            raise ValueError('SPINE_SCHEMA_VERSION_MISMATCH')
        self.sources={}
        self.concepts={}
        self.signatures={}
        self.edges=[]
        self._manifest_json=_canonical(manifest)
        for row in manifest['sources']:
            _exact(row,Source.__dataclass_fields__,'SOURCE')
            source=Source(**row)
            if (not source.id or source.id in self.sources or not source.url
                    or not source.section or source.basis not in ('OFFICIAL','AUTHOR')):
                raise ValueError('SPINE_SOURCE_IDENTITY')
            self.sources[source.id]=source
        for row in manifest['concepts']:
            _exact(row,Concept.__dataclass_fields__,'CONCEPT')
            concept=Concept(**row)
            if (not concept.id or concept.id in self.concepts or
                    concept.kind not in KINDS or concept.admission not in ADMISSION or
                    concept.source not in self.sources or not concept.name or
                    type(concept.tier) is not int or concept.tier<0 or
                    (concept.ordinal is not None and (type(concept.ordinal) is not int
                                                      or concept.ordinal<0))):
                raise ValueError('SPINE_CONCEPT_IDENTITY')
            if concept.kind in ('STEM','SLOT') and concept.ordinal is None:
                raise ValueError('SPINE_REQUIRED_ORDINAL')
            if concept.kind not in ('STEM','SLOT') and concept.ordinal is not None:
                raise ValueError('SPINE_UNEXPECTED_ORDINAL')
            if concept.admission=='SOURCE_ATTESTED' and self.sources[concept.source].basis!='OFFICIAL':
                raise ValueError('SPINE_UNTRUSTED_SOURCE_ATTESTATION')
            self.concepts[concept.id]=concept
        for row in manifest['edges']:
            _exact(row,Edge.__dataclass_fields__,'EDGE')
            edge=Edge(**row)
            if edge.source not in self.concepts or edge.target not in self.concepts:
                raise ValueError('SPINE_DANGLING_EDGE')
            if RELATIONS.get(edge.relation)!=(self.concepts[edge.source].kind,
                                             self.concepts[edge.target].kind):
                raise ValueError('SPINE_INVALID_EDGE_TYPE')
            if edge.authority not in self.sources:
                raise ValueError('SPINE_UNKNOWN_EDGE_AUTHORITY')
            if edge in self.edges:
                raise ValueError('SPINE_DUPLICATE_EDGE')
            if edge.relation=='UPGRADES' and not (
                    self.concepts[edge.target].tier>self.concepts[edge.source].tier):
                raise ValueError('SPINE_UPGRADE_NOT_PROGRESSIVE')
            self.edges.append(edge)
        for row in manifest['operators']:
            _exact(row,('id','inputs','output','source'),'OPERATOR')
            sig=Signature(row['id'],tuple(row['inputs']),row['output'],row['source'])
            if (not sig.id or sig.id in self.signatures or sig.source not in self.sources or
                    not sig.inputs or any(t not in KINDS and t!='FORMATIVE' for t in (*sig.inputs,sig.output))):
                raise ValueError('SPINE_BAD_SIGNATURE')
            self.signatures[sig.id]=sig
        self._check_root_stems()
        self._check_factor_cycles()
        self.sources=MappingProxyType(self.sources)
        self.concepts=MappingProxyType(self.concepts)
        self.signatures=MappingProxyType(self.signatures)
        self.edges=tuple(self.edges)

    def _check_root_stems(self):
        by_root={}
        assigned={}
        for edge in self.edges:
            if edge.relation=='HAS_STEM':
                by_root.setdefault(edge.source,[]).append(self.concepts[edge.target])
                if edge.target in assigned:
                    raise ValueError('SPINE_STEM_ASSIGNED_TO_MULTIPLE_ROOTS')
                assigned[edge.target]=edge.source
        for root in (c for c in self.concepts.values() if c.kind=='ROOT'):
            stems=by_root.get(root.id,[])
            if sorted(stem.ordinal for stem in stems)!=[0,1,2,3]:
                raise ValueError('SPINE_ROOT_MUST_HAVE_STEMS_ZERO_THROUGH_THREE')
        if any(concept.kind=='STEM' and concept.id not in assigned
               for concept in self.concepts.values()):
            raise ValueError('SPINE_ORPHAN_STEM')
        if len(self.edges)!=len(set(self.edges)):
            raise ValueError('SPINE_DUPLICATE_EDGES')

    def _check_factor_cycles(self):
        """Permit source-grounded sub-root decomposition without cyclic parts."""
        children={}
        for edge in self.edges:
            if edge.relation=='FACTOR_HAS_FACTOR':
                children.setdefault(edge.source,[]).append(edge.target)
        active=set()
        visited=set()

        def visit(node):
            if node in active:
                raise ValueError('SPINE_SEMANTIC_FACTOR_CYCLE')
            if node in visited:return
            active.add(node)
            for child in children.get(node,()):visit(child)
            active.remove(node)
            visited.add(node)

        for node in children:visit(node)

    def children(self,source_id,relation):
        return tuple(self.concepts[edge.target] for edge in self.edges
                     if edge.source==source_id and edge.relation==relation)

    @property
    def sha256(self):
        return hashlib.sha256(self._manifest_json.encode()).hexdigest()

    @property
    def manifest(self):
        """Defensive snapshot; caller edits cannot change the admitted graph."""
        return json.loads(self._manifest_json)


def load_seed():
    return SemanticGraph(json.loads(SEED.read_text(encoding='utf-8')))


def infer(expression: Expression, graph: SemanticGraph, depth=0) -> str:
    if depth>24:
        raise ValueError('SPINE_AST_DEPTH')
    if isinstance(expression,Atom):
        if expression.concept_id not in graph.concepts:
            raise ValueError('SPINE_UNKNOWN_ATOM')
        return graph.concepts[expression.concept_id].kind
    if not isinstance(expression,Apply) or expression.operator not in graph.signatures:
        raise ValueError('SPINE_UNKNOWN_OPERATOR')
    sig=graph.signatures[expression.operator]
    if tuple(infer(arg,graph,depth+1) for arg in expression.args)!=sig.inputs:
        raise ValueError('SPINE_AST_SIGNATURE_MISMATCH')
    if expression.operator=='COMPOSE_STEM_SPECIFICATION':
        stem=expression.args[0]
        if not isinstance(stem,Atom) or not any(e.target==stem.concept_id
            and e.relation=='HAS_STEM' for e in graph.edges):
            raise ValueError('SPINE_STEM_NOT_BOUND_TO_ROOT')
    return sig.output


def encode(expression: Expression):
    if isinstance(expression,Atom):
        return {'kind':'atom','concept':expression.concept_id}
    if isinstance(expression,Apply):
        return {'kind':'apply','operator':expression.operator,
                'args':[encode(arg) for arg in expression.args]}
    raise ValueError('SPINE_NOT_AST')


def decode(payload,graph: SemanticGraph) -> Expression:
    if not isinstance(payload,dict):
        raise ValueError('SPINE_INVALID_AST_PAYLOAD')
    if payload.get('kind')=='atom':
        _exact(payload,('kind','concept'),'AST_ATOM')
        result:Expression=Atom(payload['concept'])
    elif payload.get('kind')=='apply':
        _exact(payload,('kind','operator','args'),'AST_APPLY')
        if not isinstance(payload['args'],list):
            raise ValueError('SPINE_AST_CHILDREN_NOT_LIST')
        result=Apply(payload['operator'],tuple(decode(arg,graph) for arg in payload['args']))
    else:
        raise ValueError('SPINE_UNKNOWN_AST_KIND')
    infer(result,graph)
    return result
