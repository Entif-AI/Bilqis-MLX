"""B01 ledger ownership; historical tensor and initializer contracts retained."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from .spec import ModelTopologySpecV2
from .dimensions import FEATURE_DIM, FEATURE_ROWS, GRAPH_FEATURE_DIM, IDENTITY_BANK_SHAPE, MOTIF_PAGE_SHAPE
from .records import GenerationExtents, Initializer, ParameterCensus, ParameterGroup, ParameterSpec


def _parameter(name, shape, initializer, group=ParameterGroup.SLOW, decay=True):
    return ParameterSpec(name, shape, initializer, group, decay)

def _input_parameters() -> tuple[ParameterSpec, ...]:
    M, E, O = Initializer.MATRIX, Initializer.EMBEDDING, Initializer.ONE
    return (
        *(_parameter(f"features.{kind}", (FEATURE_ROWS, FEATURE_DIM), Initializer.FEATURE_TABLE)
          for kind in ("type", "role", "schema")),
        *(_parameter(f"features.project_{kind}", (768, FEATURE_DIM), M)
          for kind in ("type", "role", "schema")),
        _parameter("features.project_graph", (768, GRAPH_FEATURE_DIM), M),
        _parameter("features.gates", (4,), Initializer.MINUS_TWO, decay=False),
        _parameter("features.local_slot", (16, 768), E),
        _parameter("features.norm", (768,), O, decay=False),
        _parameter("frame.query_schema", (192, 128), M),
        *(_parameter(f"frame.member_{kind}", (192, 768), M) for kind in ("key", "value")),
        *(_parameter(f"frame.interact_{kind}", (192, 192), M)
          for kind in ("query", "key", "value", "output")),
        _parameter("frame.interact_norm", (192,), O, decay=False),
        _parameter("frame.project_output", (768, 192), M),
        _parameter("frame.project_summary", (768, 128), M),
        _parameter("frame.pool_gate", (1,), Initializer.MINUS_TWO, decay=False),
        _parameter("frame.empty_seed", (768,), E),
        _parameter("frame.norm", (768,), O, decay=False),
    )

def _block_parameters(index: int) -> tuple[ParameterSpec, ...]:
    M, O = Initializer.MATRIX, Initializer.ONE
    prefix = f"blocks.{index}."
    return (
        *(_parameter(prefix + name, (768,), O, decay=False) for name in ("attn_norm", "ffn_norm")),
        _parameter(prefix + "query", (384, 768), M),
        _parameter(prefix + "key", (192, 768), M),
        _parameter(prefix + "value", (192, 768), M),
        _parameter(prefix + "output", (768, 384), M),
        _parameter(prefix + "conv_q", (384, 3), Initializer.CONV_IDENTITY),
        _parameter(prefix + "conv_k", (192, 3), Initializer.CONV_IDENTITY),
        _parameter(prefix + "conv_v", (192, 3), Initializer.CONV_IDENTITY),
        _parameter(prefix + "ffn_in", (3072, 768), M),
        _parameter(prefix + "ffn_out", (768, 3072), M),
    )

def _depth_parameters(groups: int) -> tuple[ParameterSpec, ...]:
    M, O, Z = Initializer.MATRIX, Initializer.ONE, Initializer.ZERO
    return (
        _parameter("depth.norm", (768,), O, decay=False),
        *(_parameter(f"depth.{kind}", (128, 768), M) for kind in ("query", "key", "value")),
        _parameter("depth.output", (768, 128), M),
        *(item for index in range(groups) for item in (
            _parameter(f"depth.gate.{index}.vector", (768,), Z),
            _parameter(f"depth.gate.{index}.bias", (1,), Initializer.LOG_ONE_NINTH, decay=False),
        )),
    )

def _motif_site_parameters(index: int) -> tuple[ParameterSpec, ...]:
    fast = ParameterGroup.FAST
    prefix = f"motif.site.{index}."
    return (
        _parameter(prefix + "projection", (768, 128), Initializer.MATRIX, fast),
        _parameter(prefix + "norm", (768,), Initializer.ONE, fast, False),
        _parameter(prefix + "gate_hidden", (768,), Initializer.ZERO, fast),
        _parameter(prefix + "gate_feature", (128,), Initializer.ZERO, fast),
        _parameter(prefix + "bias", (1,), Initializer.MINUS_FOUR, fast, False),
    )

def _plastic_parameters(index: int) -> tuple[ParameterSpec, ...]:
    fast = ParameterGroup.FAST
    prefix = f"plastic.group.{index}."
    return (
        _parameter(prefix + "norm", (768,), Initializer.ONE, fast, False),
        _parameter(prefix + "A", (8, 768), Initializer.MATRIX, fast),
        _parameter(prefix + "B", (768, 8), Initializer.ZERO, fast),
    )

def _output_parameters() -> tuple[ParameterSpec, ...]:
    M, O, Z = Initializer.MATRIX, Initializer.ONE, Initializer.ZERO
    return (
        _parameter("refine.norm", (768,), O, decay=False),
        *(_parameter(f"refine.{kind}", (192, 768), M) for kind in ("query", "key", "value")),
        _parameter("refine.output", (768, 192), M),
        _parameter("refine.gate_vector", (768,), Z),
        _parameter("refine.bias", (1,), Initializer.LOG_ONE_NINTH, decay=False),
        _parameter("refine.route", (3, 768), M),
        _parameter("refine.route_bias", (3,), Z, decay=False),
        *(_parameter(f"readout.{kind}_norm", (768,), O, decay=False) for kind in ("state", "output")),
        *(_parameter(f"readout.{kind}", (192, 768), M) for kind in ("query", "key", "value")),
        _parameter("readout.output", (768, 192), M),
        _parameter("readout.feedback", (768, 768), M),
        _parameter("readout.role_query", (128, 768), M),
        *(item for kind, count in (("control", 4), ("epistemic", 5)) for item in (
            _parameter(f"readout.{kind}", (count, 768), M),
            _parameter(f"readout.{kind}_bias", (count,), Z, decay=False),
        )),
        *(item for kind in ("impact", "exigency", "novelty") for item in (
            _parameter(f"readout.salience.{kind}", (5, 768), M),
            _parameter(f"readout.salience_bias.{kind}", (5,), Z, decay=False),
        )),
    )

def expected_bamf_shapes(spec: ModelTopologySpecV2,
                         extents: GenerationExtents) -> tuple[ParameterSpec, ...]:
    """Expand the normative tensor ledger in stable serialization order."""
    if type(spec) is not ModelTopologySpecV2 or type(extents) is not GenerationExtents:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    return (
        *(_parameter(f"identity.bank.{bank}", IDENTITY_BANK_SHAPE, Initializer.IDENTITY_BANK,
                     ParameterGroup.IDENTITY_ROW_AGE) for bank in range(extents.semantic_bank_count)),
        *_input_parameters(),
        *(item for index in range(spec.layers) for item in _block_parameters(index)),
        *_depth_parameters(spec.depth_groups),
        *(_parameter(f"motif.page.{page}", MOTIF_PAGE_SHAPE, Initializer.MOTIF_PAGE,
                     ParameterGroup.FAST) for page in range(extents.motif_page_count)),
        *(item for index in range(2) for item in _motif_site_parameters(index)),
        *(item for index in range(spec.depth_groups) for item in _plastic_parameters(index)),
        *_output_parameters(),
    )

def bamf_parameter_census(spec: ModelTopologySpecV2, extents: GenerationExtents) -> ParameterCensus:
    declared = expected_bamf_shapes(spec, extents)
    return ParameterCensus(spec.digest, extents.digest, declared)

def print_bamf_parameter_census(spec: ModelTopologySpecV2, extents: GenerationExtents) -> ParameterCensus:
    """Print every declared tensor, category subtotal and the exact final count."""
    census = bamf_parameter_census(spec, extents)
    for item in census.parameters:
        shape = "x".join(str(value) for value in item.shape)
        print(f"TENSOR {item.name} shape={shape} parameters={item.parameter_count} category={item.category.value}")
    for category, count in census.subtotals.items():
        print(f"SUBTOTAL {category.value} {count}")
    print(f"TOTAL_PARAMETERS {census.total}")
    return census
