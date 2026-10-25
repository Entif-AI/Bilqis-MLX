"""Stage and reconcile affix observations through the existing source graph."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

if __package__:
    from . import affix_frontier as parser
else:
    import affix_frontier as parser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '_data/csv'
PROFILE = 'sources/affix_frontier_manifest.json'
LEDGER = 'sources/affix_frontier_accounting.json'
SOURCE_ID = parser.SOURCE_ID


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def read_rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def validate(data, manifest, tables, cells):
    """Check pins, full row reconciliation, exact loci and legacy compatibility."""
    subsets = {name: [row for row in rows if row['source_id'] == SOURCE_ID]
               for name, rows in [('source_tables.csv', tables), ('source_table_cells.csv', cells)]}
    profile_path = data / PROFILE
    if not profile_path.exists():
        if any(subsets.values()):
            raise ValueError('AFFIX_UNADMITTED_ROWS')
        return
    profile = json.loads(profile_path.read_text())

    def require(condition, message):
        if not condition:
            raise ValueError('AFFIX_' + message)

    require(profile.get('schema') == 'bilqis.ithkuil.affix-frontier/v1', 'PROFILE_SCHEMA')
    receipt = profile['receipt']
    source = [row for row in manifest if row['source_id'] == SOURCE_ID]
    require(len(source) == 1, 'SOURCE_IDENTITY')
    require(source[0]['sha256'] == receipt['source_sha256'] == parser.PIN, 'SOURCE_PIN')
    require(parser.PDF.is_file() and digest(parser.PDF.read_bytes()) == parser.PIN, 'SOURCE_FILE_PIN')
    require(source[0]['final_url'] == receipt['source_url'] == parser.SOURCE_URL, 'SOURCE_URL')
    require(receipt['parser_version'] == parser.PARSER_VERSION and
            receipt['parser_sha256'] == digest(Path(parser.__file__).read_bytes()), 'PARSER_IDENTITY')
    require(receipt['structure_parser_sha256'] == digest((ROOT / 'src/build_structure.py').read_bytes()),
            'STRUCTURE_PARSER_IDENTITY')
    require(receipt['page_count'] == 140 and receipt['pdf_format'] == 'PDF 1.3' and
            receipt['source_bytes'] == int(source[0]['bytes']) and
            receipt['semantic_relationships_inferred'] is False,
            'SOURCE_BOUNDARY')
    ledger_bytes = (data / LEDGER).read_bytes()
    require(digest(ledger_bytes) == receipt['observations_sha256'], 'LEDGER_DIGEST')
    ledger = json.loads(ledger_bytes)
    require(dict(sorted(Counter(row['disposition'] for row in ledger).items())) == receipt['dispositions'],
            'DISPOSITION_COUNTS')
    require(all(row['disposition'] in {'PARSED', 'UNSUPPORTED', 'CONFLICT', 'TABLE_COVERED'}
                and 1 <= row['page'] <= 140 and row.get('bbox') and len(row['bbox']) == 4
                for row in ledger), 'LEDGER_LOCUS_OR_STATE')
    require(len(ledger) == receipt['counts']['observations'], 'OBSERVATION_COUNT')
    table_observations = [row for row in ledger if row['kind'] == 'table']
    require(len(table_observations) == receipt['inventory']['detected_tables'], 'TABLE_INVENTORY')
    require(dict(sorted(Counter(row['shape'] for row in table_observations).items())) ==
            receipt['inventory']['table_shapes'], 'TABLE_SHAPES')
    require(dict(sorted(Counter(row['disposition'] for row in table_observations).items())) ==
            receipt['table_dispositions'], 'TABLE_DISPOSITIONS')
    for name, rows in subsets.items():
        key = 'table_id' if name == 'source_tables.csv' else 'cell_id'
        fields = parser.TABLE_FIELDS if key == 'table_id' else parser.CELL_FIELDS
        payload = parser.csv_bytes(rows, fields)
        require(digest(payload) == receipt['outputs'][name]['sha256'], 'OUTPUT_DIGEST:' + name)
        require(len(payload) == receipt['outputs'][name]['bytes'], 'OUTPUT_BYTES:' + name)
        require(len(rows) == receipt['counts']['tables' if key == 'table_id' else 'cells'], 'ROW_COUNT:' + name)
        emitted = [row for row in ledger if row.get('output_table') == name]
        require(len(emitted) == len(rows) and {row['output_id'] for row in emitted} ==
                {row[key] for row in rows}, 'ROW_RECONCILIATION:' + name)
        by_id = {row[key]: row for row in rows}
        for observation in emitted:
            require(observation['disposition'] == 'PARSED' and
                    parser.row_sha256(by_id[observation['output_id']]) == observation['row_sha256'],
                    'ROW_FINGERPRINT:' + observation['output_id'])
        legacy = [row for row in (tables if key == 'table_id' else cells) if row['source_id'] != SOURCE_ID]
        require(digest(csv_bytes(legacy)) == profile['legacy_sha256'][name], 'LEGACY_DRIFT:' + name)
    for name, expected in profile['output_sha256'].items():
        require(digest((data / name).read_bytes()) == expected, 'PUBLISHED_DIGEST:' + name)
    require(digest((data / 'source_sections.csv').read_bytes()) == profile['legacy_sha256']['source_sections.csv'],
            'LEGACY_SECTION_DRIFT')


def _stage_validate(data, files):
    if __package__:
        from . import validate_dataset as validator
        from .skos.preflight import preflight
    else:
        import validate_dataset as validator
        from skos.preflight import preflight
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='affix-admission-', dir=local) as directory:
        staged = Path(directory) / 'csv'
        shutil.copytree(data, staged)
        for name, payload in files.items():
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        old_data, old_sources = validator.DATA, validator.SOURCES
        try:
            validator.DATA, validator.SOURCES = staged, staged / 'sources'
            validator.main()
            preflight(staged).require_valid()
        finally:
            validator.DATA, validator.SOURCES = old_data, old_sources


def publish_files(data, files):
    _stage_validate(data, files)
    for name, payload in sorted(files.items(), key=lambda item: item[0] == PROFILE):
        path = data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(payload)
        temporary.replace(path)
        if path.read_bytes() != payload:
            raise ValueError('AFFIX_PUBLICATION_READBACK:' + name)


def admit(sections, tables, cells, data=DATA):
    # A normal HTML rebuild must reproduce the accepted legacy slice exactly.
    groups = dict(zip(('source_sections.csv', 'source_tables.csv', 'source_table_cells.csv'),
                      (sections, tables, cells)))
    legacy_hashes = {}
    for name, rows in groups.items():
        old = [row for row in read_rows(data / name) if row['source_id'] != SOURCE_ID]
        if csv_bytes(old) != csv_bytes(rows):
            raise ValueError('AFFIX_LEGACY_REBUILD_DRIFT:' + name)
        legacy_hashes[name] = digest(csv_bytes(rows))
    manifest = read_rows(data / 'sources/source_manifest.csv')
    source = next(row for row in manifest if row['source_id'] == SOURCE_ID)
    if source['sha256'] != parser.PIN or source['final_url'] != parser.SOURCE_URL:
        raise ValueError('AFFIX_MANIFEST_PIN_DRIFT')
    result = parser.extract()
    groups['source_tables.csv'] = tables + result.tables
    groups['source_table_cells.csv'] = cells + result.cells
    files = {name: csv_bytes(rows) for name, rows in groups.items()}
    files[LEDGER] = parser.canonical_bytes(result.observations)
    profile = {'schema': 'bilqis.ithkuil.affix-frontier/v1', 'receipt': result.receipt,
               'legacy_sha256': legacy_hashes,
               'output_sha256': {name: digest(payload) for name, payload in files.items()}}
    files[PROFILE] = (json.dumps(profile, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    publish_files(data, files)
    return profile
