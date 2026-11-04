"""Canonical A05 prefix identity reused by B11 execution owners."""
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.semantics.domains import contract_digest


def compiled_prefix_digest(compiled: CompiledEncoderInput) -> str:
    if type(compiled) is not CompiledEncoderInput:
        raise TypeError("compiled must be CompiledEncoderInput")
    compiled.__post_init__()
    return contract_digest((
        "bilqis.mlx.b11-compiled-prefix/v1",
        compiled.compiled.schema_version,
        tuple(row.cache_key for row in compiled.compiled.rows),
    ))
