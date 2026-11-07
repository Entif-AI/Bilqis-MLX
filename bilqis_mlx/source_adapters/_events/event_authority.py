"""Pinned source authority for the finite Ithkuil event-frame adapter."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import csv
import hashlib
from types import MappingProxyType

from ..errors import ErrorBus, SCHOOL
from ..vocabulary_growth import digest
from lib.ithkuil.src.skos.identity import sense_from_source


ROOT = Path(__file__).resolve().parents[3]


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
PROVIDER_IMPLEMENTATION_FILES = (
    'source_adapters/event_frames.py',
    'source_adapters/_events/event_authority.py',
    'source_adapters/_events/event_staging.py',
    'verification/event_frames.py',
    'factory/semantic_contrast/teaching.py',
    'factory/semantic_contrast/checker.py',
    'factory/semantic_contrast/models.py',
    'factory/semantic_contrast/transform.py',
    'factory/semantic_contrast/types.py',
)


def source_invalid(reason):
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def provider_implementation_digest(overrides=None):
    overrides = {} if overrides is None else overrides

    def source_bytes(name):
        if name in overrides:
            return overrides[name]
        if name == 'source_adapters/event_frames.py':
            return (ROOT/'bilqis_mlx/source_adapters/_events/event_frames.py').read_bytes()
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
    for capability, spec in SOURCE_SPECS.items():
        matches = tuple(row for row in rows if row['lexicon_sense_id'] == spec.sense_id)
        if len(matches) != 1:
            source_invalid('EVENT_FRAME_SOURCE_SENSE_MISSING_OR_AMBIGUOUS')
        row = matches[0]
        pdf = ROOT/'lib/ithkuil/_data/pdf'/row['tracked_pdf_name']
        _verify_source_row(capability, row, hashlib.sha256(pdf.read_bytes()).hexdigest())
        result[capability] = row
    return result


def _verify_source_row(capability, row, observed_pdf_sha256):
    spec = SOURCE_SPECS.get(capability)
    if spec is None or not isinstance(row, dict):
        source_invalid('EVENT_FRAME_SOURCE_SENSE_INVALID')
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
        source_invalid('EVENT_FRAME_SOURCE_SENSE_DRIFT')
    if observed_pdf_sha256 != spec.tracked_pdf_sha256:
        source_invalid('EVENT_FRAME_SOURCE_PDF_DRIFT')


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
        'generator': 'bilqis.ithkuil-event-frame-constructor/v1',
        'oracle': 'bilqis.issue349.event-frame-oracle/v1',
        'meaning': row['sense_summary'],
    })


def atlas_semantic_id(capability):
    """Resolve the canonical A01 atlas identity for one pinned event sense."""
    return sense_from_source('lexicon_root_senses', source_senses()[capability]).iri
