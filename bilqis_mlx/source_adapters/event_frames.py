"""Three exploratory Ithkuil senses share a finite before/after event adapter.

This models observed occurrence, inactive-to-active commencement and active-to-
inactive termination. It does not realize morphology, causation or origination.
Prototype token admissions belong only to issue349 experiments.
"""
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
import csv
import hashlib
import random
from types import MappingProxyType

from ..curriculum import AnswerFamily, BINARY
from ..factory.adapters import RegisteredSourceAdapter
from ..factory.model import SourceAdapter
from ..factory.curriculum_definition import CapabilitySpec, CapabilitySourceBinding, GradeSpec
from ..factory.executable_release import compile_executable_factory_release
from ..factory.execution import CurriculumProfile
from ..semantics.foundation.core import Apply, Operation, Signature, literal
from ..factory.verification import (
    EVENT_FRAME_ORACLE as ORACLE, event_frame_answer as independent_answer,
)
from ..vocabulary_growth import AdmittedToken, append_catalog, digest

DIALECT = 'bilqis.finite-event-frame/v1'
GENERATOR = 'bilqis.issue349.event-frames/v1'
ROOT = Path(__file__).resolve().parents[2]
SPECS = MappingProxyType({
    'D.EVENT_OCCURRENCE': ('LEXSENSE-294d00be074a56', ('A.IDENTITY',)),
    'D.COMMENCEMENT': ('LEXSENSE-45453409b348c4', ('D.EVENT_OCCURRENCE',)),
    'D.TERMINATION': ('LEXSENSE-fb0402389745d0', ('D.EVENT_OCCURRENCE','D.COMMENCEMENT')),
})
SYMBOLS = {cap: 'experiment.ithkuil.op.' + cap.split('.')[1] for cap in SPECS}
TRUE, FALSE = 'cogal.value.true', 'cogal.value.false'


@lru_cache(maxsize=1)
def source_senses():
    with (ROOT/'lib/ithkuil/_data/csv/lexicon_root_senses.csv').open() as stream:
        rows = {r['lexicon_sense_id']: r for r in csv.DictReader(stream)}
    result = {}
    for cap, (sense, _) in SPECS.items():
        row = rows[sense]
        pdf = ROOT/'lib/ithkuil/_data/pdf'/row['tracked_pdf_name']
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != row['tracked_pdf_sha256']:
            raise ValueError('EVENT_FRAME_SOURCE_PDF_DRIFT')
        result[cap] = row
    return result


def expression(graph, capability, before, after):
    symbol = SYMBOLS[capability]
    operation = Operation(graph['tokens'].index(symbol), symbol,
        Signature(('Boolean','Boolean'),'Boolean'), graph['row_contract_sha256'][symbol])
    return Apply(operation, (literal(before,'Boolean'), literal(after,'Boolean')), 'Boolean', None)


def evaluate(node):
    before, after = (arg.value for arg in node.arguments)
    cap = next(cap for cap, symbol in SYMBOLS.items() if node.operator.symbol == symbol)
    if cap == 'D.EVENT_OCCURRENCE':
        return after
    if cap == 'D.COMMENCEMENT':
        return not before and after
    return before and not after


def encode(record):
    symbols = ['micro.syntax.world', 'development.syntax.events']
    for name, before, after in record['events']:
        symbols.extend(('development.Event.'+name, TRUE if before else FALSE,
                        TRUE if after else FALSE))
    return [*symbols, 'micro.syntax.query', SYMBOLS[record['capability']],
            'development.Event.'+record['query'], 'syntax.end']


def draw(source_root, graph, *, seed, each=12, capability, **_):
    source_senses()
    if capability not in SPECS or type(each) is not int or each < 1:
        raise ValueError('EVENT_FRAME_INVALID_DRAW')
    rng = random.Random(digest((GENERATOR, seed, capability)))
    ids = {token:i for i,token in enumerate(graph['tokens'])}
    rows, seen = [], set()
    while len(rows) < each:
        names = rng.sample(['E0','E1','E2','E3'],4)
        events = [[name, bool(rng.getrandbits(1)), bool(rng.getrandbits(1))] for name in names]
        query = rng.choice(names)
        record = dict(task=DIALECT, events=events, query=query, capability=capability)
        selected = next(e for e in events if e[0]==query)
        gold = evaluate(expression(graph,capability,*selected[1:]))
        if gold != (len(rows)%2 == 0):
            continue
        identity = digest(record)
        if identity in seen:
            continue
        seen.add(identity)
        rows.append(dict(id=identity,source_id=identity,capability=capability,
            answer_kind='binary',gold='TRUE' if gold else 'FALSE',record=record,
            tokens=[ids[s] for s in encode(record)],root=SYMBOLS[capability],
            generator=GENERATOR,oracle=ORACLE,source_sense_id=SPECS[capability][0]))
    return tuple(rows)


def check(row, *, graph, **_):
    try:
        record = row['record']; cap = record['capability']
        return (row['gold']==independent_answer(record) and
            row['id']==row['source_id']==digest(record) and
            row['capability']==cap and row['source_sense_id']==SPECS[cap][0] and
            row['root']==SYMBOLS[cap] and row['generator']==GENERATOR and
            row['oracle']==ORACLE and row['answer_kind']=='binary' and
            all(type(i) is int and 0 <= i < len(graph['tokens']) for i in row['tokens']) and
            [graph['tokens'][i] for i in row['tokens']]==encode(record))
    except (KeyError,TypeError,ValueError,IndexError):
        return False


def registered_adapter():
    fingerprint = digest({name:hashlib.sha256((ROOT/'bilqis_mlx'/name).read_bytes()).hexdigest()
        for name in ('source_adapters/event_frames.py','verification/event_frames.py')})
    return RegisteredSourceAdapter(SourceAdapter('source.issue349.event-frames/v1',
        GENERATOR,(ORACLE,),fingerprint,
        variation_axes=('event-identity','before-state','after-state','fact-order','fresh-seed')),
        draw,check,witness=lambda row,obligation,**kw: check(row,**kw) and
            obligation.key in SPECS[row['capability']][1])


def expanded_graph(parent):
    sources = source_senses(); admissions = []
    for cap, (sense, prereqs) in SPECS.items():
        if SYMBOLS[cap] in parent['tokens']:
            continue
        row = sources[cap]; proof = digest((GENERATOR, sense, row['source_text_sha256']))
        admissions.append(AdmittedToken(SYMBOLS[cap], 'experiment:349/'+sense+'/event-frame/v1',
            row['sense_summary']+'; exploratory finite event observation/transition only',
            'new_ithkuil','compositional',row['source_url'],row['source_text_sha256'],
            proof,registered_adapter().descriptor.implementation_sha256,
            ('development.Event.E0',),cap,proof,signature='Boolean*Boolean->Boolean',arity=2))
    return append_catalog(parent,tuple(admissions),allow_disposable_fixtures=True)[0] if admissions else parent


def compile_tranche(current, graph, *, source_root, source_registry, answer_registry):
    """A small experimental factory instance; existing runtime owns execution."""
    sources = source_senses()
    caps = tuple(CapabilitySpec(cap,'finite-event-frame',(SYMBOLS[cap],),(SYMBOLS[cap],),
        prerequisites,(),(AnswerFamily('binary',BINARY),))
        for cap,(_,prerequisites) in SPECS.items())
    grade = GradeSpec('D',caps,tuple((cap,12) for cap in SPECS),
        tuple((cap,) for cap in SPECS))
    curriculum = replace(current.curriculum,grades=(*current.curriculum.grades,grade))
    bindings = replace(current.source_bindings,bindings=(*current.source_bindings.bindings,
        *(CapabilitySourceBinding(cap,'ithkuil:sense/'+sense+'@sha256:'+sources[cap]['source_text_sha256'],
            GENERATOR,ORACLE) for cap,(sense,_) in SPECS.items())))
    return compile_executable_factory_release(curriculum,bindings,
        CurriculumProfile('issue349/pathfinding-events/v1',grades=current.profile.grades),
        source_registry,answer_registry,source_root=source_root,graph=graph,
        verification_seed=349,predecessor=current)
