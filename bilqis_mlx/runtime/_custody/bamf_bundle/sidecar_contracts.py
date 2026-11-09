"""B13-owned storage-envelope versions and declared identity cross-bindings.

These envelopes preserve supplied JSON fields/values, not upstream artifact bytes
or source admission authority. Motif, plasticity and outbox retain their own codecs.
"""
from collections.abc import Mapping
from types import MappingProxyType

SOURCE_BINDING_WIDTH = 2

SCHEMAS = MappingProxyType({
    'semantic_abi': 'bilqis.mlx.bamf-semantic-abi/v1',
    'compiler_features': 'bilqis.mlx.bamf-compiler-features/v1',
    'correction_frontier': 'bilqis.mlx.bamf-correction-frontier/v1',
    'teacher_state': 'bilqis.mlx.bamf-teacher-state/v1',
    'evaluation_contract': 'bilqis.mlx.bamf-evaluation-contract/v1',
    'step_proofs': 'bilqis.mlx.bamf-step-proofs/v1',
})


def _digest(value):
    return (type(value) is str and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


def _epoch(value):
    return type(value) is int and value >= 0


def _validate_feature_binding(compiler, invalid):
    """Keep recorded source/schema bindings shape-checked when they are present.

    Absence stays legal for historical generations; the accepted-generation
    feature authority refuses any generation that cannot replay its feature
    map from the admitted source release.
    """
    source = compiler.get('feature_source')
    if source is not None and (
            not isinstance(source, dict)
            or set(source) != {'atlas_bundle_id', 'release_sha256', 'source_bundle_id'}
            or any(not _digest(source[name]) for name in source)):
        invalid()
    schema = compiler.get('feature_schema')
    if schema is not None and (
            not isinstance(schema, dict)
            or set(schema) != {'role_ids', 'schema_ids', 'source_bindings'}
            or not isinstance(schema['role_ids'], list)
            or not isinstance(schema['schema_ids'], list)
            or not isinstance(schema['source_bindings'], list)
            or any(not isinstance(row, list) or len(row) != SOURCE_BINDING_WIDTH
                   or not all(isinstance(value, str) and value for value in row)
                   for row in schema['source_bindings'])):
        invalid()
    grades = compiler.get('factory_grade_ids')
    if grades is not None and (
            not isinstance(grades, list) or not grades
            or len(set(grades)) != len(grades)
            or any(type(grade) is not str or not grade for grade in grades)):
        invalid()


def validate_identity_sidecars(extents, provenance, records, invalid):
    """Reject absent ownership identities before constructing any tensor state."""
    if any(records[name].get('schema') != schema for name, schema in SCHEMAS.items()):
        invalid()
    semantic = records['semantic_abi']
    compiler = records['compiler_features']
    proofs = records.get('step_proofs')
    if proofs is not None and proofs.get('schema') != SCHEMAS['step_proofs']:
        invalid()
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
    _validate_feature_binding(compiler, invalid)
    source_authority_anchor = correction.get('source_authority_registry_sha256')
    if (source_authority_anchor is not None and not _digest(source_authority_anchor)):
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
