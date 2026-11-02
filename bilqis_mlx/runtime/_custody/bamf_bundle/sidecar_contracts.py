"""B13-owned storage-envelope versions and declared identity cross-bindings.

These envelopes preserve supplied JSON fields/values, not upstream artifact bytes
or source admission authority. Motif, plasticity and outbox retain their own codecs.
"""
from collections.abc import Mapping
from types import MappingProxyType

SCHEMAS = MappingProxyType({
    'semantic_abi': 'bilqis.mlx.bamf-semantic-abi/v1',
    'compiler_features': 'bilqis.mlx.bamf-compiler-features/v1',
    'correction_frontier': 'bilqis.mlx.bamf-correction-frontier/v1',
    'teacher_state': 'bilqis.mlx.bamf-teacher-state/v1',
    'evaluation_contract': 'bilqis.mlx.bamf-evaluation-contract/v1',
})


def _digest(value):
    return (type(value) is str and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


def _epoch(value):
    return type(value) is int and value >= 0


def validate_identity_sidecars(extents, provenance, records, invalid):
    """Reject absent ownership identities before constructing any tensor state."""
    if any(records[name].get('schema') != schema for name, schema in SCHEMAS.items()):
        invalid()
    semantic = records['semantic_abi']
    compiler = records['compiler_features']
    correction = records['correction_frontier']
    teacher = records['teacher_state']
    banks = semantic.get('bank_identities')
    if (type(semantic.get('semantic_bank_count')) is not int
            or semantic['semantic_bank_count'] != extents.semantic_bank_count
            or semantic.get('active_set_sha256') != extents.active_semantic_digest
            or type(banks) not in (tuple, list) or len(banks) != extents.semantic_bank_count
            or not all(type(bank) is str and bank.strip() and bank.isprintable() for bank in banks)
            or len(set(banks)) != len(banks)):
        invalid()
    if (compiler.get('factor_map_sha256') != extents.factor_map_digest
            or not _digest(compiler.get('compiler_sha256'))
            or any(not _epoch(record.get(key)) for record, keys in (
                (compiler, ('rights_epoch', 'correction_generation')),
                (correction, ('rights_epoch', 'correction_generation')),
                (teacher, ('teacher_epoch', 'next_seed')),
            ) for key in keys)
            or correction.get('rights_epoch') != compiler['rights_epoch']
            or correction.get('correction_generation') != compiler['correction_generation']
            or correction.get('source_identity') != provenance.source_identity
            or correction.get('release_digest') != provenance.release_digest
            or not isinstance(correction.get('frontier'), (list, Mapping))
            or teacher.get('teacher_identity') != provenance.teacher_identity
            or teacher.get('teacher_epoch') != provenance.teacher_epoch
            or not _digest(records['evaluation_contract'].get('contract_sha256'))):
        invalid()
