"""Revalidate source atoms and derive all supported compiled vectors in B01 custody."""
from ...semantics.source_atom_binding.common import invalid
from ..frame_embeddings import ConceptBatch, embed_atoms
from ..frame_encoder import (
    CompiledEncoderInput, CompiledEmbeddingVectors, MemberEmbedding, encode_frames,
)
from .embedding import source_atom_vectors


def encode_source_compiled(compiled, parameters, sources, feature_schema):
    """Encode actual A05 rows without accepting arbitrary atom or member vectors.

    Native atomic-frame closures need their own source-to-identity law and stay
    held. Raw atoms, complete ordinary frames and verified nested frames use
    existing B02/B03 operations. This does not issue B11 producer admission.
    """
    if (type(compiled) is not CompiledEncoderInput or type(sources) is not tuple
            or len(sources) != len(compiled.compiled.rows)):
        invalid("BAMF_SOURCE_ATOM_COMPILED_INPUT_INVALID")
    compiled.__post_init__()
    if any(compiled.atomic_handles):
        invalid("BAMF_SOURCE_ATOM_ATOMIC_FRAME_AUTHORITY_UNAVAILABLE")
    atom_rows, member_rows = [], []
    for row, config, source, requests in zip(
            compiled.compiled.rows, compiled.compiler_configs,
            sources, compiled.member_requests):
        vectors, banks, _ = source_atom_vectors(
            parameters, row, config, source, compiled.features,
            feature_schema, compiled.extents)
        atom_rows.append(vectors)
        if requests:
            members = embed_atoms(
                parameters, ConceptBatch((requests,), banks, compiled.extents),
                compiled.features)[0]
            member_rows.append(tuple(MemberEmbedding(request, members[index])
                                     for index, request in enumerate(requests)))
        else:
            member_rows.append(())
    generated = CompiledEmbeddingVectors(tuple(atom_rows), tuple(member_rows))
    return encode_frames(compiled, generated, parameters)
