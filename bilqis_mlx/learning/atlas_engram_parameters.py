"""B07.4 read-only motif parameter view over the complete B01 tensor ledger."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    validate_bamf_parameters,
)


VIEW_SCHEMA = "bilqis.mlx.motif-parameter-view/v1"
_VIEW_SEAL = object()
SITE_NAMES = ("projection", "norm", "gate_hidden", "gate_feature", "bias")
SITE_COUNT = 2


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class MotifParameterView(Mapping[str, mx.array]):
    """Sealed differentiable copy-on-read tensors, never trainable aliases."""

    __source_tensors: Mapping[str, mx.array]
    site_index: int
    page_count: int
    _seal: object
    schema_version: str = VIEW_SCHEMA

    def __post_init__(self) -> None:
        expected = {f"page.{index}" for index in range(self.page_count)}
        expected.update(SITE_NAMES)
        if (self._seal is not _VIEW_SEAL
                or type(self.site_index) is not int
                or not 0 <= self.site_index < SITE_COUNT
                or type(self.page_count) is not int
                or not 1 <= self.page_count <= ModelTopologySpecV2.max_motif_pages
                or set(self.__source_tensors) != expected
                or self.schema_version != VIEW_SCHEMA):
            _invalid()
        object.__setattr__(
            self, "_MotifParameterView__source_tensors",
            MappingProxyType(dict(self.__source_tensors)))

    def __getitem__(self, name: str) -> mx.array:
        # mx.array creates a differentiable COW handle. In-place writes to a
        # returned value cannot mutate the B01-owned parameter or other sites.
        return mx.array(self.__source_tensors[name])

    def __iter__(self):
        return iter(self.__source_tensors)

    def __len__(self) -> int:
        return len(self.__source_tensors)


def motif_parameter_view(
    parameters: Mapping[str, mx.array], *,
    spec: ModelTopologySpecV2, extents: GenerationExtents, site_index: int,
) -> MotifParameterView:
    """Validate the full B01 tree, then borrow only motif-owned named tensors."""
    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(site_index) is not int
            or not 0 <= site_index < SITE_COUNT):
        _invalid()
    validate_bamf_parameters(spec, extents, parameters)
    declared = {item.name: item for item in expected_bamf_shapes(spec, extents)}
    pages = {f"page.{index}": f"motif.page.{index}"
             for index in range(extents.motif_page_count)}
    site = {name: f"motif.site.{site_index}.{name}" for name in SITE_NAMES}
    all_motif_names = {
        *(f"motif.page.{index}" for index in range(extents.motif_page_count)),
        *(f"motif.site.{index}.{name}"
          for index in range(SITE_COUNT) for name in SITE_NAMES),
    }
    if ({name for name in declared if name.startswith("motif.")}
            != all_motif_names
            or any(name not in declared for name in (*pages.values(), *site.values()))):
        _invalid()
    return MotifParameterView(
        {local: parameters[name] for local, name in {**pages, **site}.items()},
        site_index, extents.motif_page_count, _VIEW_SEAL)
