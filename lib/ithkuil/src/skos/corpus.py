"""Compose existing domain builds and independently census their source rows."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from .atomic import compile_atomic
from .atomic_reconcile import reconcile_atomic
from .build import LIB_ROOT, PROFILE_VERSION
from .composition import load_composition_profile
from .coverage import build_coverage
from .extension_vocabulary import load_extension_vocabulary
from .lexicon_reconcile import reconcile_lexicon_frontier
from .mapping_corpus import compile_mapping_corpus
from .no_omission import SourceRowIdentity
from .preflight import preflight
from .residue_reconcile import reconcile_residue

SOURCE_TABLES = (
    ('atomic', 'morphemes_atomic', 'atomic_id'),
    ('lexicon', 'lexicon_roots', 'lexicon_root_id'),
    ('lexicon', 'lexicon_root_senses', 'lexicon_sense_id'),
    ('lexicon', 'lexicon_root_evidence', 'lexicon_evidence_id'),
    ('residue', 'affix_degrees', 'degree_id'),
    ('residue', 'morpheme_compositions', 'composition_id'),
    ('residue', 'composition_components', 'component_id'),
    ('residue', 'allomorph_rules', 'allomorph_rule_id'),
    ('mapping', 'bilqis_ithkuil_crosswalk', 'crosswalk_id'),
    ('mapping', 'bilqis_semantic_bridges', 'bridge_id'),
)


def _rows(root, name):
    with (Path(root) / (name + '.csv')).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def source_census(root):
    return tuple(sorted(SourceRowIdentity(domain, table, row[key])
                        for domain, table, key in SOURCE_TABLES for row in _rows(root, table)))


def compile_domains(root):
    """Orchestrate the #68 domain owners without changing projection decisions."""
    root = Path(root)
    closure = preflight(root).require_valid()
    atomic = compile_atomic(closure)
    fixtures = LIB_ROOT / 'tests/fixtures'
    lexicon = reconcile_lexicon_frontier(
        root, relation_profile_path=LIB_ROOT / 'src/skos/root_sense_extension.json',
        negative_fixture_path=fixtures / 'skos_root_sense_negative.ttl',
    )
    profile = load_composition_profile(LIB_ROOT / 'src/skos/composition_profile.json', closure,
                                       fixtures / 'skos_composition_negative.ttl')
    vocabulary = load_extension_vocabulary(LIB_ROOT / 'src/skos/extension_vocabulary.json', root)
    residue = reconcile_residue(
        closure, degree_rows=_rows(root, 'affix_degrees'),
        component_rows=_rows(root, 'composition_components'), allomorph_rows=_rows(root, 'allomorph_rules'),
        composition_profile=profile, vocabulary=vocabulary,
    )
    mapping = compile_mapping_corpus(root)
    return build_coverage(
        closure, atomic_compiled=atomic, atomic_reconciliation=reconcile_atomic(closure, atomic),
        lexicon=lexicon, residue=residue, mapping=mapping, profile_version=PROFILE_VERSION,
        profile_sha256=hashlib.sha256((LIB_ROOT / 'SKOS_PROFILE.md').read_bytes()).hexdigest(),
    ), mapping.graph
