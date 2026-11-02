"""Receipts for source-owned partial forests."""
from __future__ import annotations
from dataclasses import dataclass
import re
from ..domains import contract_digest
from ..frame_compiler import _invalid
from ..frame_schema import FrameTree


PARTIAL_PARENT_SCHEMA = "bilqis.partial-visible-parent/v1"
PARTIAL_FOREST_SCHEMA = "bilqis.partial-visible-forest-receipt/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class HiddenParentProvenance:
    """Non-visible parent authority without future member content."""

    child_occurrence_id: str
    parent_occurrence_id: str
    parent_frame_handle: str
    provenance_digest: str
    schema_version: str = PARTIAL_PARENT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(isinstance(item, str) and _SHA.fullmatch(item)
                    for item in (
                        self.child_occurrence_id,
                        self.parent_occurrence_id,
                        self.provenance_digest))
                or not isinstance(self.parent_frame_handle, str)
                or not self.parent_frame_handle
                or self.schema_version != PARTIAL_PARENT_SCHEMA):
            _invalid("BAMF_PREFIX_PARTIAL_PARENT_INVALID")



def _visible_tree_identity(tree: FrameTree) -> tuple:
    return (
        tree.root.occurrence_id,
        tree.root.content_digest,
        tuple(_visible_tree_identity(child) for child in tree.children),
    )



def _partial_forest_digest(
    source_instance_id: str,
    semantic_release: str,
    visible_end: int,
    compiler_cache_key: str,
    visible_forest: tuple[FrameTree, ...],
    visible_frame_handles: tuple[tuple[str, str], ...],
    hidden_parents: tuple[HiddenParentProvenance, ...],
) -> str:
    return contract_digest((
        PARTIAL_FOREST_SCHEMA,
        source_instance_id,
        semantic_release,
        visible_end,
        compiler_cache_key,
        tuple(_visible_tree_identity(tree) for tree in visible_forest),
        visible_frame_handles,
        tuple((
            item.child_occurrence_id,
            item.parent_occurrence_id,
            item.parent_frame_handle,
            item.provenance_digest,
        ) for item in hidden_parents),
    ))



@dataclass(frozen=True)
class PartialVisibleForestReceipt:
    """Visible frame forest plus opaque provenance for non-visible parents."""

    source_instance_id: str
    semantic_release: str
    visible_end: int
    compiler_cache_key: str
    visible_forest: tuple[FrameTree, ...]
    visible_frame_handles: tuple[tuple[str, str], ...]
    hidden_parents: tuple[HiddenParentProvenance, ...]
    digest: str
    schema_version: str = PARTIAL_FOREST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or type(self.visible_end) is not int or self.visible_end < 0
                or not isinstance(self.compiler_cache_key, str)
                or not _SHA.fullmatch(self.compiler_cache_key)
                or not isinstance(self.visible_forest, tuple)
                or any(not isinstance(tree, FrameTree)
                       for tree in self.visible_forest)
                or not isinstance(self.visible_frame_handles, tuple)
                or any(not isinstance(item, tuple) or len(item) != 2
                       or not isinstance(item[0], str) or not _SHA.fullmatch(item[0])
                       or not isinstance(item[1], str) or not item[1]
                       for item in self.visible_frame_handles)
                or not isinstance(self.hidden_parents, tuple)
                or any(not isinstance(item, HiddenParentProvenance)
                       for item in self.hidden_parents)
                or not isinstance(self.digest, str) or not _SHA.fullmatch(self.digest)
                or self.digest != _partial_forest_digest(
                    self.source_instance_id,
                    self.semantic_release,
                    self.visible_end,
                    self.compiler_cache_key,
                    self.visible_forest,
                    self.visible_frame_handles,
                    self.hidden_parents)
                or self.schema_version != PARTIAL_FOREST_SCHEMA):
            _invalid("BAMF_PREFIX_PARTIAL_RECEIPT_INVALID")
