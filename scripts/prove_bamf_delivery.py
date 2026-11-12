"""C13.1 disposable integrated-delivery fixture and bounded preflight API.

This module prepares source-visible episode-binding cases and immutable witness
metadata. It never opens the retained learner or claims neural-learning success.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import random

from bilqis_mlx.errors import ErrorBus, SCHOOL

_CONFIG_SCHEMA = "bilqis.c13.delivery-config/v1"
_SOURCE_SCHEMA = "bilqis.c13.episode-source-release/v1"
_CASE_SCHEMA = "bilqis.c13.episode-binding-case/v1"
_RECEIPT_SCHEMA = "bilqis.c13.delivery-receipt/v1"
_MAX_STEPS = 64
_ACTORS = ("A", "B", "C")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


def _digest(value: object) -> str:
    wire = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(wire.encode()).hexdigest()


@dataclass(frozen=True)
class DeliveryConfig:
    baseline_seeds: tuple[int, ...] = tuple(range(64))
    fresh_seeds: tuple[int, ...] = tuple(range(64, 128))
    depths: tuple[int, ...] = (1, 2, 3, 4)
    schema_version: str = _CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != _CONFIG_SCHEMA
                or self.baseline_seeds != tuple(range(64))
                or self.fresh_seeds != tuple(range(64, 128))
                or self.depths != (1, 2, 3, 4)):
            _fail("BAMF_C13_DELIVERY_CONFIG_INVALID")


@dataclass(frozen=True)
class EpisodeSourceRelease:
    release_sha256: str
    semantic_release: str
    source_family_id: str = "bamf.c13.episode-binding/v1"
    schema_version: str = _SOURCE_SCHEMA

    def __post_init__(self) -> None:
        values = (self.release_sha256, self.semantic_release)
        if (self.schema_version != _SOURCE_SCHEMA
                or any(not isinstance(value, str) or len(value) != 64
                       or any(char not in "0123456789abcdef" for char in value)
                       for value in values)
                or not self.source_family_id):
            _fail("BAMF_C13_SOURCE_RELEASE_INVALID")


@dataclass(frozen=True)
class EpisodeEvent:
    actor: str
    ordinal: int
    start_minute: int
    duration_minutes: int

    def __post_init__(self) -> None:
        if (self.actor not in _ACTORS or self.ordinal not in (0, 1)
                or type(self.start_minute) is not int or self.start_minute < 0
                or type(self.duration_minutes) is not int
                or self.duration_minutes <= 0):
            _fail("BAMF_C13_EPISODE_EVENT_INVALID")


@dataclass(frozen=True)
class EpisodeBindingCase:
    seed: int
    depth: int
    events: tuple[EpisodeEvent, ...]
    cue_actor: str
    query_kind: str
    schema_version: str = _CASE_SCHEMA

    def __post_init__(self) -> None:
        keys = tuple((event.actor, event.ordinal) for event in self.events)
        if (self.schema_version != _CASE_SCHEMA or type(self.seed) is not int
                or self.seed < 0 or self.depth not in (1, 2, 3, 4)
                or self.cue_actor not in _ACTORS
                or self.query_kind not in ("LATER_DURATION", "SUM_DURATIONS")
                or len(self.events) != 6 or len(set(keys)) != 6
                or set(actor for actor, _ in keys) != set(_ACTORS)):
            _fail("BAMF_C13_EPISODE_CASE_INVALID")

    def source_view(self) -> dict:
        """Gold-blind model-visible task: relation cue, facts and legal intent only."""
        return {
            "schema": _CASE_SCHEMA,
            "source_family_id": "bamf.c13.episode-binding/v1",
            "seed": self.seed,
            "depth": self.depth,
            "actors": list(_ACTORS),
            "events": [asdict(event) for event in self.events],
            "relation_cue": {
                "kind": "FIRST_EVENT_SUCCESSOR",
                "from_actor": self.cue_actor,
                "hops": self.depth,
            },
            "query": self.query_kind,
            "task_goal_shape": {
                "candidate_binding_hole": "Entity",
                "continuation": (
                    ["ROLE_LOOKUP", "SELECT_NUMBER"]
                    if self.query_kind == "LATER_DURATION"
                    else ["ROLE_LOOKUP", "SELECT_NUMBER", "ADD"]
                ),
                "gold_binding_in_model_input": False,
            },
        }


@dataclass(frozen=True)
class DeliveryReceipt:
    source_release_sha256: str
    semantic_release: str
    fixture_manifest_sha256: str
    baseline_case_count: int
    fresh_case_count: int
    max_steps: int
    status: str
    exercised_behaviors: tuple[str, ...]
    remaining_behaviors: tuple[str, ...]
    schema_version: str = _RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != _RECEIPT_SCHEMA
                or self.status not in ("PREPARED", "EXECUTED")
                or self.baseline_case_count != 64 or self.fresh_case_count != 64
                or not 0 <= self.max_steps <= _MAX_STEPS
                or len(self.fixture_manifest_sha256) != 64):
            _fail("BAMF_C13_DELIVERY_RECEIPT_INVALID")


def episode_binding_case(seed: int, depth: int = 1) -> EpisodeBindingCase:
    if type(seed) is not int or seed < 0 or depth not in (1, 2, 3, 4):
        _fail("BAMF_C13_EPISODE_SEED_INVALID")
    rng = random.Random(seed)
    order = list(_ACTORS)
    rng.shuffle(order)
    starts = {actor: position * 10 + rng.randrange(0, 3)
              for position, actor in enumerate(order)}
    events = tuple(
        EpisodeEvent(actor, ordinal, starts[actor] + ordinal * 5,
                     1 + rng.randrange(1, 10))
        for actor in _ACTORS for ordinal in (0, 1)
    )
    cue_actor = order[0]
    kind = "LATER_DURATION" if seed % 2 == 0 else "SUM_DURATIONS"
    return EpisodeBindingCase(seed, depth, events, cue_actor, kind)


def check_episode_binding(case: EpisodeBindingCase) -> int:
    """Independent source checker. The selected actor is never stored in source_view."""
    if type(case) is not EpisodeBindingCase:
        _fail("BAMF_C13_EPISODE_CHECK_INPUT_INVALID")
    first = {event.actor: event.start_minute for event in case.events
             if event.ordinal == 0}
    ordered = tuple(sorted(_ACTORS, key=lambda actor: (first[actor], actor)))
    start = ordered.index(case.cue_actor)
    target = ordered[(start + case.depth) % len(ordered)]
    durations = tuple(event.duration_minutes for event in case.events
                      if event.actor == target)
    return durations[1] if case.query_kind == "LATER_DURATION" else sum(durations)


def _fixture_manifest(config: DeliveryConfig, source: EpisodeSourceRelease) -> dict:
    baseline = tuple(episode_binding_case(seed, 1) for seed in config.baseline_seeds)
    fresh = tuple(episode_binding_case(seed, 1) for seed in config.fresh_seeds)
    rows = lambda cases: [
        {"input": case.source_view(), "checker_answer": check_episode_binding(case)}
        for case in cases
    ]
    return {
        "schema": "bilqis.c13.disposable-fixture-manifest/v1",
        "source_release_sha256": source.release_sha256,
        "semantic_release": source.semantic_release,
        "baseline": rows(baseline),
        "fresh": rows(fresh),
    }


def _disposable(path: Path) -> Path:
    root = path.expanduser().resolve()
    retained = (Path(__file__).resolve().parents[1] / "runs").resolve()
    if root == retained or retained in root.parents:
        _fail("BAMF_C13_RETAINED_RUN_PATH_FORBIDDEN")
    root.mkdir(parents=True, exist_ok=True)
    return root


def prove_bamf_delivery(config, source_release, disposable_dir, max_steps) -> DeliveryReceipt:
    """Prepare the C13 witness deterministically; later leaves own neural execution."""
    if (type(config) is not DeliveryConfig
            or type(source_release) is not EpisodeSourceRelease
            or type(max_steps) is not int or not 0 <= max_steps <= _MAX_STEPS):
        _fail("BAMF_C13_DELIVERY_ARGUMENT_INVALID")
    root = _disposable(Path(disposable_dir))
    manifest = _fixture_manifest(config, source_release)
    manifest_path = root / "c13-source-fixtures.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    remaining = (
        "SOURCE_BOUND_GRADIENTS", "PAIRED_EVALUATION", "ACCEPTED_CANDIDATE",
        "REJECTED_CANDIDATE", "COLD_RESTART", "APPEND_ONLY_SEMANTIC_DELTA",
    )
    return DeliveryReceipt(
        source_release.release_sha256, source_release.semantic_release, digest,
        64, 64, max_steps, "PREPARED", ("DISPOSABLE_CREATION",), remaining)


__all__ = (
    "DeliveryConfig", "DeliveryReceipt", "EpisodeBindingCase", "EpisodeEvent",
    "EpisodeSourceRelease", "check_episode_binding", "episode_binding_case",
    "prove_bamf_delivery",
)
