"""Learning-first ahead-preparation identities and candidate-local caches."""
from dataclasses import dataclass, field
from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.runtime.bamf_bundle import is_authenticated_generation_feature_context
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.semantics.domains import contract_digest
from .atlas_training_contracts import _invalid
from .factory_training_source import _prepare_learning_first_model_sources
from .learning_first_source import prepare_learning_first_source_rows

@dataclass(frozen=True)
class LearningFirstPreparedSourceInputs:
    """Generation-independent row/model inputs prepared ahead of neural execution."""

    identity: str
    binding: tuple
    rows_sha256: str
    source_seed: int
    source_each: int
    source_rows: tuple
    model_sources: tuple
    source_identity: str | None = None


def _learning_first_preparation_binding(source_context, authenticated) -> tuple:
    return (
        source_context.release.release_sha256,
        authenticated.snapshot.release_sha256,
        authenticated.snapshot.bundle_id,
        authenticated.snapshot.source_bundle_id,
        authenticated.features.semantic_release,
        authenticated.features.digest,
    )


def _learning_first_preparation_identity(
        binding, rows_sha256: str, source_seed: int, source_each: int) -> str:
    return contract_digest({
        "schema": "bilqis.mlx.learning-first-ahead-preparation/v1",
        "binding": binding, "rows_sha256": rows_sha256,
        "source_seed": source_seed, "source_each": source_each,
    })


def prepare_learning_first_source_inputs_ahead(
        source_context, authenticated, rows, *, source_seed: int, source_each: int,
        source_identity: str | None = None, content_digest_fn=content_digest):
    """Prepare only source/model inputs that do not depend on optimizer state."""
    rows = tuple(rows)
    if (type(source_context) is not SourceExecutionContext
            or not is_authenticated_generation_feature_context(authenticated)
            or not rows or any(type(row) is not dict for row in rows)
            or type(source_seed) is not int or source_seed < 0
            or type(source_each) is not int or source_each < 1
            or (source_identity is not None and (
                not isinstance(source_identity, str) or len(source_identity) != 64
                or any(char not in "0123456789abcdef" for char in source_identity)))):
        _invalid("LEARNING_FIRST_AHEAD_PREPARATION_INVALID")
    binding = _learning_first_preparation_binding(source_context, authenticated)
    # CandidateSourceLane has already authenticated the exact packet. Reuse that
    # identity instead of re-hashing the complete row payload on the overlapped
    # ordinary host-preparation path. Direct callers without a packet identity
    # retain the content digest as the conservative fallback.
    rows_sha256 = (
        source_identity if source_identity is not None else content_digest_fn(rows))
    source_rows = prepare_learning_first_source_rows(
        source_context, authenticated, rows,
        source_seed=source_seed, source_each=source_each)
    model_sources = _prepare_learning_first_model_sources(authenticated, source_rows)
    identity = _learning_first_preparation_identity(
        binding, rows_sha256, source_seed, source_each)
    return LearningFirstPreparedSourceInputs(
        identity, binding, rows_sha256, source_seed, source_each,
        source_rows, model_sources, source_identity)


def _prepared_ahead_matches(
        prepared, source_context, authenticated, rows, *, source_seed, source_each,
        source_identity=None, content_digest_fn=content_digest):
    if type(prepared) is not LearningFirstPreparedSourceInputs:
        return False
    rows = tuple(rows)
    binding = _learning_first_preparation_binding(source_context, authenticated)
    packet_bound = source_identity is not None
    if packet_bound:
        if (not isinstance(source_identity, str) or len(source_identity) != 64
                or any(char not in "0123456789abcdef" for char in source_identity)
                or prepared.source_identity != source_identity):
            return False
        rows_sha256 = prepared.rows_sha256
    else:
        rows_sha256 = content_digest_fn(rows)
    expected_identity = _learning_first_preparation_identity(
        binding, rows_sha256, source_seed, source_each)
    if (prepared.identity != expected_identity
            or prepared.binding != binding
            or prepared.rows_sha256 != rows_sha256
            or prepared.source_seed != source_seed
            or prepared.source_each != source_each
            or len(prepared.source_rows) != len(rows)
            or len(prepared.model_sources) != len(rows)):
        return False
    for row, source_row, model_source in zip(
            rows, prepared.source_rows, prepared.model_sources, strict=True):
        if (getattr(source_row, "row", None) != row
                or getattr(model_source, "row_id", None) != row.get("id")
                or getattr(model_source, "visible", None) != tuple(row.get("tokens", ()))
                or getattr(model_source, "eligibility_digest", None)
                   != getattr(getattr(source_row, "projection", None), "digest", None)):
            return False
    return True


@dataclass
class LearningFirstPreparationCache:
    """Candidate-local reuse of exact row preparation for ordinary learning."""

    _binding: tuple | None = None
    _rows: dict = field(default_factory=dict)
    _task_inputs: dict = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    task_hits: int = 0
    task_misses: int = 0

    def bind(self, source_context, authenticated) -> None:
        binding = (
            str(source_context.run_dir),
            source_context.release.release_sha256,
            authenticated.snapshot.release_sha256,
            authenticated.snapshot.bundle_id,
            authenticated.snapshot.source_bundle_id,
            authenticated.features.semantic_release,
            authenticated.features.digest,
        )
        if self._binding is None:
            self._binding = binding
        elif self._binding != binding:
            self._binding = binding
            self._rows.clear()
            self._task_inputs.clear()

    @staticmethod
    def key(row, eligibility_digest=None):
        row_id = row.get("id") if isinstance(row, dict) else None
        if not isinstance(row_id, str) or not row_id:
            _invalid("LEARNING_FIRST_PREPARATION_ROW_ID_REQUIRED")
        return row_id, eligibility_digest

    def get(self, row, eligibility_digest):
        value = self._rows.get(self.key(row, eligibility_digest))
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
        return value

    def put(self, row, eligibility_digest, model_source) -> None:
        self._rows[self.key(row, eligibility_digest)] = model_source

    def get_task_inputs(self, key):
        value = self._task_inputs.get(key)
        if value is None:
            self.task_misses += 1
        else:
            self.task_hits += 1
        return value

    def put_task_inputs(self, key, value) -> None:
        self._task_inputs[key] = value
