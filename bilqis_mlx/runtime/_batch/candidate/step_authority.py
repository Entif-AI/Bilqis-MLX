"""O(1) process-local authority for ordinary learning-first candidate steps."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from threading import RLock
from time import perf_counter
import weakref

from bilqis_mlx.errors import ErrorBus, SCHOOL


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_TRAINING_ADAPTER.INVALID, reason=reason)


@dataclass
class _Owner:
    cache_ref: weakref.ReferenceType
    epoch: int = 0
    token: str | None = None


@dataclass(frozen=True)
class LearningFirstStepAuthority:
    token: str
    cache_id: int
    cache_ref: weakref.ReferenceType
    parent_ref: weakref.ReferenceType
    candidate_ref: weakref.ReferenceType | None
    optimizer: object = field(repr=False, compare=False)
    parameters: object = field(repr=False, compare=False)
    source_context: object = field(repr=False, compare=False)
    accepted_run_id: str
    accepted_generation: int
    accepted_generation_binding: str
    accepted_candidate_identity_sha256: str
    accepted_manifest_sha256: str
    release_sha256: str
    source_authority_registry_sha256: str | None
    topology_digest: str
    extents_digest: str
    optimizer_step: int
    candidate_step: int
    epoch: int
    speculative: bool


class _Registry:
    """Single process-local mutable owner for disposable step authority."""

    def __init__(self):
        self.lock = RLock()
        self.owners: dict[int, _Owner] = {}
        self.tokens: dict[str, LearningFirstStepAuthority] = {}
        self.candidate_tokens: dict[int, tuple[weakref.ReferenceType, str]] = {}
        self.parameter_tokens: dict[int, str] = {}
        self.metrics = {
            "learning_first_step_token_issues": 0,
            "learning_first_step_token_hits": 0,
            "learning_first_step_token_misses": 0,
            "learning_first_step_full_proof_fallbacks": 0,
            "learning_first_step_token_issue_wall_seconds": 0.0,
            "learning_first_step_token_require_wall_seconds": 0.0,
        }


_REGISTRY = _Registry()
_LOCK = _REGISTRY.lock
_OWNERS = _REGISTRY.owners
_TOKENS = _REGISTRY.tokens
_CANDIDATE_TOKENS = _REGISTRY.candidate_tokens
_PARAMETER_TOKENS = _REGISTRY.parameter_tokens
_METRICS = _REGISTRY.metrics


def _cleanup_owner(key: int, reference) -> None:
    with _LOCK:
        owner = _OWNERS.get(key)
        if owner is None or owner.cache_ref is not reference:
            return
        if owner.token is not None:
            _drop_token(owner.token)
        _OWNERS.pop(key, None)


def _cleanup_candidate(key: int, reference) -> None:
    with _LOCK:
        current = _CANDIDATE_TOKENS.get(key)
        if current is not None and current[0] is reference:
            _CANDIDATE_TOKENS.pop(key, None)


def _drop_token(token: str) -> None:
    authority = _TOKENS.pop(token, None)
    if authority is None:
        return
    if _PARAMETER_TOKENS.get(id(authority.parameters)) == token:
        _PARAMETER_TOKENS.pop(id(authority.parameters), None)
    if authority.candidate_ref is not None:
        candidate = authority.candidate_ref()
        if candidate is not None:
            current = _CANDIDATE_TOKENS.get(id(candidate))
            if current is not None and current[1] == token:
                _CANDIDATE_TOKENS.pop(id(candidate), None)


def _owner_for(cache) -> _Owner:
    key = id(cache)
    owner = _OWNERS.get(key)
    if owner is not None and owner.cache_ref() is cache:
        return owner
    reference = weakref.ref(cache, lambda ref, key=key: _cleanup_owner(key, ref))
    owner = _Owner(reference)
    _OWNERS[key] = owner
    return owner


def _token_for(*, cache, parent, candidate, optimizer, release_sha256: str, epoch: int) -> str:
    candidate_step = 0 if candidate is None else candidate.update_steps
    raw = "|".join((
        "bilqis.learning-first-step-authority/v1",
        cache.run_id,
        str(cache.generation),
        cache.accepted_manifest_sha256,
        cache.generation_binding,
        cache._candidate_identity_sha256,
        release_sha256,
        cache.source_authority_registry_sha256 or "",
        parent.topology.digest,
        parent.extents.digest,
        str(parent.retained_state.optimizer_step + candidate_step),
        str(candidate_step),
        str(epoch),
        str(id(optimizer)),
        str(id(optimizer.parameters)),
    )).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def issue_learning_first_step_authority(cache, parent, candidate, source_context) -> str:
    """Issue one opaque current-step token without reading model tensor bytes."""
    started = perf_counter()
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import require_accepted_execution_cache
    from bilqis_mlx.learning._atlas_candidate.transaction import CandidateTransaction
    from bilqis_mlx.runtime.bamf_bundle.records import CompleteStudent

    cache = require_accepted_execution_cache(cache)
    if type(parent) is not CompleteStudent:
        _invalid("LEARNING_FIRST_STEP_AUTHORITY_PARENT_INVALID")
    if candidate is not None and (
            type(candidate) is not CandidateTransaction
            or not candidate.learning_first
            or candidate.parent is not parent.retained_state):
        _invalid("LEARNING_FIRST_STEP_AUTHORITY_CANDIDATE_DRIFT")
    release_sha256 = source_context.release.release_sha256
    if not isinstance(release_sha256, str) or not release_sha256:
        _invalid("LEARNING_FIRST_STEP_AUTHORITY_RELEASE_IDENTITY_REQUIRED")
    accepted_identity = getattr(cache, "_candidate_identity_sha256", None)
    if not isinstance(accepted_identity, str) or not accepted_identity:
        _invalid("LEARNING_FIRST_STEP_AUTHORITY_ACCEPTED_IDENTITY_REQUIRED")
    optimizer = parent.retained_state.optimizer if candidate is None else candidate.optimizer
    with _LOCK:
        owner = _owner_for(cache)
        owner.epoch += 1
        if owner.token is not None:
            _drop_token(owner.token)
        token = _token_for(
            cache=cache, parent=parent, candidate=candidate, optimizer=optimizer,
            release_sha256=release_sha256, epoch=owner.epoch)
        authority = LearningFirstStepAuthority(
            token=token, cache_id=id(cache), cache_ref=owner.cache_ref,
            parent_ref=weakref.ref(parent),
            candidate_ref=None if candidate is None else weakref.ref(candidate),
            optimizer=optimizer, parameters=optimizer.parameters,
            source_context=source_context,
            accepted_run_id=cache.run_id,
            accepted_generation=cache.generation,
            accepted_generation_binding=cache.generation_binding,
            accepted_candidate_identity_sha256=accepted_identity,
            accepted_manifest_sha256=cache.accepted_manifest_sha256,
            release_sha256=release_sha256,
            source_authority_registry_sha256=cache.source_authority_registry_sha256,
            topology_digest=parent.topology.digest,
            extents_digest=parent.extents.digest,
            optimizer_step=parent.retained_state.optimizer_step
            + (0 if candidate is None else candidate.update_steps),
            candidate_step=0 if candidate is None else candidate.update_steps,
            epoch=owner.epoch,
            speculative=candidate is not None,
        )
        owner.token = token
        _TOKENS[token] = authority
        _PARAMETER_TOKENS[id(authority.parameters)] = token
        if candidate is not None:
            reference = weakref.ref(
                candidate,
                lambda ref, key=id(candidate): _cleanup_candidate(key, ref),
            )
            _CANDIDATE_TOKENS[id(candidate)] = (reference, token)
        _METRICS["learning_first_step_token_issues"] += 1
        _METRICS["learning_first_step_token_issue_wall_seconds"] += (
            perf_counter() - started)
    return token


def current_learning_first_step_authority_for_candidate(candidate) -> str | None:
    """Return the live authority token for this exact transaction, if any."""
    with _LOCK:
        current = _CANDIDATE_TOKENS.get(id(candidate))
        if current is None or current[0]() is not candidate:
            return None
        token = current[1]
    require_learning_first_step_authority(token)
    return token


def current_learning_first_step_authority_for_parameters(parameters) -> str | None:
    """Return the live speculative authority for this exact parameter mapping."""
    with _LOCK:
        token = _PARAMETER_TOKENS.get(id(parameters))
        authority = None if token is None else _TOKENS.get(token)
        if authority is None or authority.parameters is not parameters:
            return None
    require_learning_first_step_authority(token, parameters=parameters)
    return token


def bind_learning_first_step_authority(cache, parent, candidate, source_context) -> str:
    """Reuse unchanged speculative authority; issue only when state actually changed."""
    if candidate is not None:
        token = current_learning_first_step_authority_for_candidate(candidate)
        if token is not None:
            return token
    return issue_learning_first_step_authority(cache, parent, candidate, source_context)


def require_learning_first_step_authority(token: str, *, parameters=None,
                                          topology_digest: str | None = None,
                                          extents_digest: str | None = None
                                          ) -> LearningFirstStepAuthority:
    """Require the latest token for its exact optimizer tree in O(1)."""
    started = perf_counter()
    try:
        with _LOCK:
            authority = _TOKENS.get(token)
            if authority is None:
                _METRICS["learning_first_step_token_misses"] += 1
                _invalid("LEARNING_FIRST_STEP_AUTHORITY_MISSING_OR_STALE")
            owner = _OWNERS.get(authority.cache_id)
            cache = authority.cache_ref()
            parent = authority.parent_ref()
            candidate = (
                None if authority.candidate_ref is None
                else authority.candidate_ref()
            )
            if (owner is None or owner.cache_ref() is not authority.cache_ref()
                    or owner.token != token or owner.epoch != authority.epoch
                    or cache is None
                    or parent is None
                    or (authority.candidate_ref is not None
                        and candidate is None)
                    or cache.run_id != authority.accepted_run_id
                    or cache.generation != authority.accepted_generation
                    or cache.accepted_manifest_sha256
                       != authority.accepted_manifest_sha256
                    or cache.generation_binding
                       != authority.accepted_generation_binding
                    or getattr(cache, "_candidate_identity_sha256", None)
                       != authority.accepted_candidate_identity_sha256
                    or cache.source_authority_registry_sha256
                       != authority.source_authority_registry_sha256
                    or authority.source_context.release.release_sha256
                       != authority.release_sha256
                    or parent.topology.digest != authority.topology_digest
                    or parent.extents.digest != authority.extents_digest
                    or (candidate is None
                        and (parent.retained_state.optimizer is not authority.optimizer
                             or parent.retained_state.optimizer_step
                             != authority.optimizer_step))
                    or (candidate is not None
                        and (candidate.parent is not parent.retained_state
                             or candidate.optimizer is not authority.optimizer
                             or candidate.update_steps != authority.candidate_step
                             or parent.retained_state.optimizer_step
                                + candidate.update_steps
                                != authority.optimizer_step))
                    or authority.optimizer.parameters is not authority.parameters
                    or (parameters is not None and parameters is not authority.parameters)
                    or (topology_digest is not None
                        and topology_digest != authority.topology_digest)
                    or (extents_digest is not None
                        and extents_digest != authority.extents_digest)):
                _METRICS["learning_first_step_token_misses"] += 1
                _invalid("LEARNING_FIRST_STEP_AUTHORITY_DRIFT")
            _METRICS["learning_first_step_token_hits"] += 1
            return authority
    finally:
        with _LOCK:
            _METRICS["learning_first_step_token_require_wall_seconds"] += (
                perf_counter() - started)


def learning_first_step_authority_exists(token: str) -> bool:
    with _LOCK:
        return token in _TOKENS


def record_learning_first_full_proof_fallback() -> None:
    with _LOCK:
        _METRICS["learning_first_step_full_proof_fallbacks"] += 1


def learning_first_step_authority_metrics_snapshot() -> dict:
    with _LOCK:
        return dict(_METRICS)


def learning_first_step_authority_metrics_delta(before: dict) -> dict:
    after = learning_first_step_authority_metrics_snapshot()
    return {key: after[key] - before.get(key, 0) for key in after}


def _reset_learning_first_step_authority_for_tests() -> None:
    with _LOCK:
        _OWNERS.clear()
        _TOKENS.clear()
        _CANDIDATE_TOKENS.clear()
        _PARAMETER_TOKENS.clear()
        for key, value in _METRICS.items():
            _METRICS[key] = 0.0 if isinstance(value, float) else 0
