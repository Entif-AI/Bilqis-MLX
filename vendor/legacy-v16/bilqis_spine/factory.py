"""One semantic grammar produces teaching and assessment instances.

This is a structural-concept prototype, not an Ithkuil spelling generator or
a linguistically complete semantic oracle. Both channels compile from the
same admitted graph; they receive independent seeds and durable receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import random
from types import MappingProxyType

from .model import Apply, Atom, SemanticGraph, encode, infer

TASKS = ('IDENTIFY_STEM','CONSTRUCT_FORMATIVE','DISTINGUISH_DIMENSION')
OUTPUT = MappingProxyType({'IDENTIFY_STEM':'CONCEPT_ID',
          'CONSTRUCT_FORMATIVE':'TYPED_AST',
          'DISTINGUISH_DIMENSION':'DIMENSION_ID'})
SKILLS = ('BILQIS.SKILL.STEM.1','BILQIS.SKILL.STEM.2',
          'BILQIS.SKILL.STEM.3','BILQIS.SKILL.STEM.4')


@dataclass(frozen=True)
class Question:
    id: str
    semantic_spine_sha256: str
    channel: str
    seed: int
    skill: str
    task: str
    answer_kind: str
    input: dict
    gold: str | dict
    provenance: tuple[str,...]

    def packet(self):
        return {'id':self.id,'semantic_spine_sha256':self.semantic_spine_sha256,
                'channel':self.channel,'seed':self.seed,'skill':self.skill,
                'task':self.task,'answer_kind':self.answer_kind,
                'input':self.input,'gold':self.gold,
                'provenance':list(self.provenance)}


def _stem(graph, root, ordinal):
    matches=[node for node in graph.children(root,'HAS_STEM') if node.ordinal==ordinal]
    if len(matches)!=1:
        raise ValueError('SPINE_UNRESOLVED_STEM')
    return matches[0].id


def _spec(graph):
    specs=[c.id for c in graph.concepts.values() if c.kind=='SPECIFICATION']
    return sorted(specs)


def _build(graph, stem, spec, manifest=None):
    expression=Apply('COMPOSE_STEM_SPECIFICATION',(Atom(stem),Atom(spec)))
    if manifest is not None:
        expression=Apply('MARK_MANIFESTATION',(expression,Atom(manifest)))
    if infer(expression,graph)!='FORMATIVE':
        raise ValueError('SPINE_INVALID_FORMATIVE')
    return encode(expression)


def _dimension(left,right):
    """Compare controlled AST coordinates, not cross-language paraphrases."""
    differences=[name for name in ('stem','specification','manifestation')
                 if left[name]!=right[name]]
    if len(differences)!=1:
        raise ValueError('SPINE_CONTRAST_NOT_MINIMAL')
    return differences[0].upper()


class QuestionFactory:
    def __init__(self,graph:SemanticGraph):
        self.graph=graph

    def generate(self,*,tier:int,seed:int,count:int=12,channel:str='lesson'):
        if (type(tier) is not int or tier not in (1,2,3) or
                type(seed) is not int or seed<0 or type(count) is not int
                or count<1 or channel not in ('lesson','assessment')):
            raise ValueError('SPINE_UNSUPPORTED_GENERATION_REQUEST')
        skill=SKILLS[tier-1]
        if skill not in self.graph.concepts:
            raise ValueError('SPINE_UNKNOWN_SKILL')
        seed_bytes=json.dumps([seed,channel,self.graph.sha256,tier]).encode()
        rng=random.Random(int.from_bytes(sha256(seed_bytes).digest()[:8],'big'))
        roots=sorted(c.id for c in self.graph.concepts.values() if c.kind=='ROOT')
        specs=_spec(self.graph)
        manifest=sorted(c.id for c in self.graph.concepts.values()
                        if c.kind=='MANIFESTATION')
        if not roots or not specs or not manifest:
            raise ValueError('SPINE_NO_SOURCE_BACKED_GENERATION_CATALOG')
        eligible=TASKS[:tier]
        result=[]
        for i in range(count):
            task=eligible[i%len(eligible)]
            root=rng.choice(roots)
            ordinal=rng.randrange(4)
            stem=_stem(self.graph,root,ordinal)
            spec=rng.choice(specs)
            mode=rng.choice(manifest)
            if task=='IDENTIFY_STEM':
                prompt={'root':root,'requested_stem_position':ordinal}
                gold=stem
                support=(self.graph.concepts[stem].source,)
            elif task=='CONSTRUCT_FORMATIVE':
                prompt={'stem':stem,'specification':spec}
                gold=_build(self.graph,stem,spec)
                support=(self.graph.concepts[stem].source,
                         self.graph.concepts[spec].source)
            else:
                before={'stem':stem,'specification':spec,'manifestation':mode}
                after=dict(before)
                # Curriculum coverage of contrast TYPES is deterministic;
                # the semantic operands and encounter identities still vary.
                dimension=('stem','specification','manifestation')[(i//len(eligible))%3]
                if dimension=='stem':
                    after[dimension]=_stem(self.graph,root,(ordinal+rng.randrange(1,4))%4)
                elif dimension=='specification':
                    after[dimension]=rng.choice([s for s in specs if s!=spec])
                else:
                    after[dimension]=rng.choice([m for m in manifest if m!=mode])
                prompt={'left':_build(self.graph,before['stem'],before['specification'],
                                       before['manifestation']),
                        'right':_build(self.graph,after['stem'],after['specification'],
                                        after['manifestation'])}
                gold=_dimension(before,after)
                support=(self.graph.concepts[stem].source,
                         self.graph.concepts[spec].source,
                         self.graph.concepts[mode].source)
            packet={'spine':self.graph.sha256,'channel':channel,'seed':seed,
                    'index':i,'task':task,'prompt':prompt,'skill':skill}
            identity=sha256(json.dumps(packet,sort_keys=True,separators=(',',':'))
                            .encode()).hexdigest()
            result.append(Question(identity,self.graph.sha256,channel,seed,skill,
                                   task,OUTPUT[task],prompt,gold,
                                   tuple(sorted(set(support)))))
        return tuple(result)


def coverage(examples):
    """Show exactly which task/answer types teaching and exam contain."""
    tasks={q.task for q in examples}
    return {'tasks':sorted(tasks),
            'answer_kinds':sorted({q.answer_kind for q in examples}),
            'contrast_dimensions':sorted({q.gold for q in examples
                                          if q.task=='DISTINGUISH_DIMENSION'}),
            'size':len(examples),
            'spine_hashes':sorted({q.semantic_spine_sha256 for q in examples})}


def validate_same_contract(lessons,exams):
    """Fail before grading when an assessment uses an untaught task type."""
    left,right=coverage(lessons),coverage(exams)
    if (left['spine_hashes']!=right['spine_hashes'] or
            not set(right['tasks']).issubset(left['tasks']) or
            not set(right['answer_kinds']).issubset(left['answer_kinds']) or
            not set(right['contrast_dimensions']).issubset(left['contrast_dimensions'])):
        raise ValueError('SPINE_UNTAUGHT_ASSESSMENT_SURFACE')
    if ({q.id for q in lessons}&{q.id for q in exams}):
        raise ValueError('SPINE_LESSON_ASSESSMENT_EXACT_INSTANCE_COLLISION')
    return True
