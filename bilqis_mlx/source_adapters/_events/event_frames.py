"""Three source-qualified Ithkuil senses share a finite before/after event adapter.

This models observed occurrence, inactive-to-active commencement and active-to-
inactive termination. It does not realize morphology, causation or origination.
Catalog additions remain neural-inert proposals until the BAMF admission owner
accepts them; this module owns only source semantics, generation and checking.
"""
from dataclasses import dataclass, replace
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
from ..factory.candidate_staging import candidate_source_anchor, compile_candidate_successor
from ..factory.executable_release import compile_executable_factory_release
from ..factory.execution import CurriculumProfile
from ..semantics.core import Apply, Operation, Signature, literal
from ..factory.verification import (
    EVENT_FRAME_ORACLE as ORACLE, event_frame_answer as independent_answer,
)
from ..factory.semantic_contrast.teaching import (
    OPTION_ID as SEMANTIC_CONTRAST_OPTION,
    check_contrast_row,
    contrast_semantic_footprint,
    enrich_contrasts,
)
from ..errors import ErrorBus, SCHOOL
from ..vocabulary_growth import AdmittedToken, append_catalog, digest
from lib.ithkuil.src.skos.identity import sense_from_source

DIALECT = 'bilqis.finite-event-frame/v1'
GENERATOR = 'bilqis.ithkuil-event-frame-constructor/v1'
ADAPTER_ID = 'source.ithkuil-event-frames/v1'
ROOT = Path(__file__).resolve().parents[3]
_BALANCE_MODULUS = 2


@dataclass(frozen=True)
class EventSourceSpec:
    sense_id: str
    root_id: str
    root_form: str
    source_text_sha256: str
    tracked_pdf_sha256: str
    prerequisites: tuple[str, ...]


SOURCE_SPECS = MappingProxyType({
    'D.EVENT_OCCURRENCE': EventSourceSpec(
        'LEXSENSE-294d00be074a56', 'LEXROOT-78a8d2e5e8f911', '-PS-',
        '4ad21b82d3b0ff9f8bedbfb12efb7184cead6cb5ad549cc88c6626e0ec1b0dd7',
        '0d8eaa667d26345dfb55e99ee823fb8ecfa4b4a2d72f998d0e0e3c7b94bad9b2',
        ('A.IDENTITY',)),
    'D.COMMENCEMENT': EventSourceSpec(
        'LEXSENSE-45453409b348c4', 'LEXROOT-cf61519c142b35', '-TĻ-',
        '4546ed26bfd8763da86c897ef03e7567d8117497af9ad8f6923fbd7c39df676d',
        '0d8eaa667d26345dfb55e99ee823fb8ecfa4b4a2d72f998d0e0e3c7b94bad9b2',
        ('D.EVENT_OCCURRENCE',)),
    'D.TERMINATION': EventSourceSpec(
        'LEXSENSE-fb0402389745d0', 'LEXROOT-0762c2b024374a', '-MPR-',
        '0a9c0af53457cd758c2ec3f3cac87b684d883a5076cd3949fd3c888d25c75a9e',
        '0d8eaa667d26345dfb55e99ee823fb8ecfa4b4a2d72f998d0e0e3c7b94bad9b2',
        ('D.EVENT_OCCURRENCE', 'D.COMMENCEMENT')),
})
SPECS = MappingProxyType({
    capability: (spec.sense_id, spec.prerequisites)
    for capability, spec in SOURCE_SPECS.items()
})
SYMBOLS = MappingProxyType({
    capability: 'ithkuil.op.' + capability.split('.')[1]
    for capability in SOURCE_SPECS
})
SEMANTIC_IDS = MappingProxyType({
    capability: f'ithkuil:{spec.sense_id}/finite-event-frame/v1'
    for capability, spec in SOURCE_SPECS.items()
})
TRUE, FALSE = 'cogal.value.true', 'cogal.value.false'
PROVIDER_IMPLEMENTATION_FILES = (
    'source_adapters/event_frames.py',
    'verification/event_frames.py',
    'factory/semantic_contrast/teaching.py',
    'factory/semantic_contrast/checker.py',
    'factory/semantic_contrast/models.py',
    'factory/semantic_contrast/transform.py',
    'factory/semantic_contrast/types.py',
)


def _source_invalid(reason):
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def provider_implementation_digest(overrides=None):
    overrides = {} if overrides is None else overrides
    def source_bytes(name):
        if name in overrides:
            return overrides[name]
        if name == 'source_adapters/event_frames.py':
            return Path(__file__).read_bytes()
        return (ROOT/'bilqis_mlx'/name).read_bytes()
    return digest({
        name: hashlib.sha256(source_bytes(name)).hexdigest()
        for name in PROVIDER_IMPLEMENTATION_FILES
    })


@lru_cache(maxsize=1)
def source_senses():
    with (ROOT/'lib/ithkuil/_data/csv/lexicon_root_senses.csv').open() as stream:
        rows = tuple(csv.DictReader(stream))
    result = {}
    for cap, spec in SOURCE_SPECS.items():
        matches = tuple(row for row in rows if row['lexicon_sense_id'] == spec.sense_id)
        if len(matches) != 1:
            _source_invalid('EVENT_FRAME_SOURCE_SENSE_MISSING_OR_AMBIGUOUS')
        row = matches[0]
        pdf = ROOT/'lib/ithkuil/_data/pdf'/row['tracked_pdf_name']
        _verify_source_row(cap, row, hashlib.sha256(pdf.read_bytes()).hexdigest())
        result[cap] = row
    return result


def _verify_source_row(capability, row, observed_pdf_sha256):
    spec = SOURCE_SPECS.get(capability)
    if spec is None or not isinstance(row, dict):
        _source_invalid('EVENT_FRAME_SOURCE_SENSE_INVALID')
    expected = {
        'lexicon_sense_id': spec.sense_id,
        'lexicon_root_id': spec.root_id,
        'root_form_raw': spec.root_form,
        'stem': 'STEM 1',
        'specification': 'BSC',
        'source_text_sha256': spec.source_text_sha256,
        'tracked_pdf_sha256': spec.tracked_pdf_sha256,
        'source_url': 'https://ithkuil.net/New_Ithkuil_Lexicon.pdf',
    }
    if any(row.get(key) != value for key, value in expected.items()):
        _source_invalid('EVENT_FRAME_SOURCE_SENSE_DRIFT')
    if observed_pdf_sha256 != spec.tracked_pdf_sha256:
        _source_invalid('EVENT_FRAME_SOURCE_PDF_DRIFT')


def source_contract_digest(capability):
    row = source_senses()[capability]
    spec = SOURCE_SPECS[capability]
    return digest({
        'schema': 'bilqis.ithkuil-event-frame-source/v1',
        'capability': capability,
        'semantic_id': SEMANTIC_IDS[capability],
        'symbol': SYMBOLS[capability],
        'sense_id': spec.sense_id,
        'source_text_sha256': spec.source_text_sha256,
        'tracked_pdf_sha256': spec.tracked_pdf_sha256,
        'prerequisites': spec.prerequisites,
        'signature': 'Boolean*Boolean->Boolean',
        'generator': GENERATOR,
        'oracle': ORACLE,
        'meaning': row['sense_summary'],
    })


def atlas_semantic_id(capability):
    """Resolve the canonical A01 atlas identity for one pinned event sense."""
    return sense_from_source('lexicon_root_senses', source_senses()[capability]).iri


def capability_definition(capability):
    """Return the ordinary Factory capability declaration for one event sense."""
    spec = SOURCE_SPECS[capability]
    return CapabilitySpec(
        capability, 'finite-event-frame', (SYMBOLS[capability],), (SYMBOLS[capability],),
        spec.prerequisites, (), (AnswerFamily('binary', BINARY),),
    )


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
        if gold != (len(rows) % _BALANCE_MODULUS == 0):
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
    if row.get('generator') == SEMANTIC_CONTRAST_OPTION:
        return check_contrast_row(row, graph=graph)
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


def semantic_footprint(row):
    if row.get('generator') == SEMANTIC_CONTRAST_OPTION:
        return contrast_semantic_footprint(row)
    root = row.get('root')
    if not isinstance(root, str) or not root:
        from ..errors import ErrorBus, SCHOOL
        ErrorBus.raise_(
            SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
            reason='EVENT_FRAME_SEMANTIC_FOOTPRINT_INVALID',
        )
    return (root,)


def registered_adapter():
    return RegisteredSourceAdapter(SourceAdapter(ADAPTER_ID,
        GENERATOR,(ORACLE,),provider_implementation_digest(),
        variation_axes=('event-identity','before-state','after-state','fact-order','fresh-seed'),
        teaching_option_ids=(SEMANTIC_CONTRAST_OPTION,)),
        draw,check,
        witness=lambda row,obligation,**kw: check(row,**kw) and
            row.get('generator') == GENERATOR and
            obligation.key in SPECS[row['capability']][1],
        enrich=enrich_contrasts,
        semantic_footprint=semantic_footprint)


def projected_graph(parent, capabilities):
    """Append only the requested prerequisite-closed event identities."""
    if (type(capabilities) is not tuple or not capabilities
            or len(set(capabilities)) != len(capabilities)
            or any(capability not in SOURCE_SPECS for capability in capabilities)):
        _source_invalid('EVENT_FRAME_CATALOG_PROJECTION_INVALID')
    sources = source_senses(); admissions = []
    available = set(parent.get('tokens', ()))
    for cap in capabilities:
        sense, prereqs = SPECS[cap]
        if SYMBOLS[cap] in parent['tokens']:
            available.add(SYMBOLS[cap])
            continue
        required_event_tokens = tuple(
            SYMBOLS[item] for item in prereqs if item in SYMBOLS)
        if any(token not in available for token in required_event_tokens):
            _source_invalid('EVENT_FRAME_CATALOG_PREREQUISITE_MISSING')
        row = sources[cap]; proof = source_contract_digest(cap)
        if cap == 'D.EVENT_OCCURRENCE':
            prerequisite_tokens = ('development.Event.E0',)
        else:
            prerequisite_tokens = required_event_tokens
        admissions.append(AdmittedToken(SYMBOLS[cap], SEMANTIC_IDS[cap],
            row['sense_summary']+'; finite event observation/transition only; morphology not realized',
            'new_ithkuil','compositional',row['source_url'],row['source_text_sha256'],
            proof,registered_adapter().descriptor.implementation_sha256,
            prerequisite_tokens,cap,proof,signature='Boolean*Boolean->Boolean',arity=2))
        available.add(SYMBOLS[cap])
    return append_catalog(parent,tuple(admissions),allow_disposable_fixtures=True)[0] if admissions else parent


def expanded_graph(parent):
    return projected_graph(parent, tuple(SOURCE_SPECS))


def stage_capability(
    frontier, current, parent_graph, capability, *,
    source_root, source_registry, answer_registry,
):
    """Stage exactly one prerequisite-closed event successor without admitting it."""
    spec = SOURCE_SPECS.get(capability)
    matches = [
        candidate for candidate in frontier.candidates
        if candidate.proposed_capability_id == capability
        and spec is not None and candidate.target_sense_id == spec.sense_id
    ]
    if (spec is None or capability in current.curriculum.capability_map
            or len(matches) != 1):
        _source_invalid('EVENT_FRAME_EXACT_NEW_CANDIDATE_REQUIRED')
    if any(prerequisite not in current.curriculum.capability_map
           for prerequisite in spec.prerequisites):
        _source_invalid('EVENT_FRAME_FACTORY_PREREQUISITE_MISSING')

    candidate_id = matches[0].candidate_id
    event_capability = capability_definition(capability)
    grades = list(current.curriculum.grades)
    for index, grade in enumerate(grades):
        if grade.grade_id != 'D':
            continue
        grades[index] = replace(
            grade,
            capabilities=(*grade.capabilities, event_capability),
            exam_item_counts=(*grade.exam_item_counts, (capability, 12)),
            teaching_stages=(*grade.teaching_stages, (capability,)),
        )
        break
    else:
        grades.append(GradeSpec('D', (event_capability,), ((capability, 12),), ((capability,),)))
    curriculum = replace(current.curriculum, grades=tuple(grades))
    bindings = replace(
        current.source_bindings,
        bindings=(*current.source_bindings.bindings, CapabilitySourceBinding(
            capability, candidate_source_anchor(frontier, candidate_id), GENERATOR, ORACLE)),
    )
    graph = projected_graph(parent_graph, (capability,))
    profile = CurriculumProfile('jit/event-frames/v1', grades=current.profile.grades)
    staged = compile_candidate_successor(
        frontier, current, candidate_id,
        curriculum=curriculum, source_bindings=bindings, profile=profile,
        source_registry=source_registry, answer_registry=answer_registry,
        source_root=source_root, graph=graph, verification_seed=2026110704,
    )
    staged.successor.verify_semantic_catalog(graph)
    return staged


def compile_tranche(current, graph, *, source_root, source_registry, answer_registry):
    """Compile the three source-qualified event capabilities without admitting them."""
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
        CurriculumProfile('bamf/event-frames/v1',grades=current.profile.grades),
        source_registry,answer_registry,source_root=source_root,graph=graph,
        verification_seed=2026110703,predecessor=current)
