"""A05.4 source-owned validation for causally partial visible frame forests."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .context_eligibility import (
    ContextEligibility,
    ContextHold,
    check_context_eligibility,
)
from .domains import contract_digest
from .frame_compiler import (
    CompiledFrameBatch,
    FrameCompilerConfig,
    StreamingAST,
    _closure_end,
    _invalid,
    compile_prefix,
    reconstruct,
)
from .frame_schema import (
    AtomicFrame,
    FrameInstance,
    FrameSchema,
    FrameTree,
    validate_frame_tree,
)


from ._partial_forest.receipts import (
    HiddenParentProvenance, _visible_tree_identity, _partial_forest_digest,
    PartialVisibleForestReceipt, PARTIAL_PARENT_SCHEMA, PARTIAL_FOREST_SCHEMA,
    _SHA,
)
from ._partial_forest.source import (
    _source_tree_index, _visible_forest_frames,
)
from ._partial_forest.provenance import (
    _hidden_parent_provenance,
)
from ._partial_forest.authority import (
    _validate_hidden_parent_current_authority,
)


from ._partial_forest.validation import validate_partial_visible_forest


# Preserve public receipt and callable identities across source owners.
for _public in (
    validate_partial_visible_forest,
    HiddenParentProvenance, _visible_tree_identity, _partial_forest_digest,
    PartialVisibleForestReceipt, _source_tree_index, _visible_forest_frames,
    _hidden_parent_provenance, _validate_hidden_parent_current_authority,
):
    _public.__module__ = __name__
