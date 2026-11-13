"""Canonical A05 prefix identity reused by B11 execution owners."""
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.semantics.domains import contract_digest


def compiled_prefix_digest(compiled: CompiledEncoderInput) -> str:
    if type(compiled) is not CompiledEncoderInput:
        ErrorBus.Raise(
            SCHOOL.MODEL_TOPOLOGY.INVALID,
            reason="B11_COMPILED_PREFIX_INPUT_INVALID",
        )
    compiled.__post_init__()
    return contract_digest((
        "bilqis.mlx.b11-compiled-prefix/v1",
        compiled.compiled.schema_version,
        tuple(row.cache_key for row in compiled.compiled.rows),
    ))
