"""Public C09 correction/revalidation surface.

Implementation is split by authority, evidence records, queue state and pure engine
operations so the public API stays stable without one oversized owner module.
"""
from ._revalidation_base import (
    CORRECTION_EVENT_SCHEMA, REVALIDATED_ARTIFACT_SCHEMA,
    REVALIDATION_FRONTIER_SCHEMA, REVALIDATION_TASK_SCHEMA,
    REVALIDATION_QUEUE_SCHEMA, STATE_TRANSITION_SCHEMA,
    REVALIDATION_PROGRESS_SCHEMA, SOURCE_AUTHORITY_SCOPE_SCHEMA,
    SOURCE_AUTHORITY_KEY_SCHEMA, SOURCE_AUTHORITY_REGISTRY_SCHEMA,
    MAX_REVALIDATION_PRIORITY, _canonical_bytes, _digest, _invalid, _name,
    _refs_payload, _time,
)
from ._revalidation_events import CorrectionEvent, RevalidatedArtifact, RevalidationFrontier
from ._revalidation_queue import (
    RevalidationTask, StateTransition, RevalidationQueue, RevalidationProgress,
)
from ._revalidation_authority import (
    SourceAuthorityScope, SourceAuthorityKey, SourceAuthorityRegistry,
)
from ._revalidation_engine import (
    apply_correction, read_artifact, next_revalidation_task, revalidate_node,
    advance_revalidation,
)
from .atlas_cache_owner import ExactCacheArtifactOwner, cache_artifact_digest

__all__ = tuple(name for name in globals() if not name.startswith("__"))
