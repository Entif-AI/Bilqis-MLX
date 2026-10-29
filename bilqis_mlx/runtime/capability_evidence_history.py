"""Immutable historical score bytes and separate non-learning translations."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Callable

from ..errors import BilqisError
from ..semantics.foundation.domains import contract_digest
from .capability_retention import Assessment, _invalid, _names, _sha
from .cognitive_solver import SOLVE_REPLAY_SCHEMA
from .operator_registry import RouteKind
from ..semantics.cognitive_dag import DAGReceipt
from ..semantics.cognitive_operators import ValueState

HISTORY_SCHEMA = "bilqis.c05.frozen-assessment/v1"
TRANSLATION_SCHEMA = "bilqis.c05.translation/v1"
TRANSLATOR_SCHEMA = "bilqis.c05.translator/v1"


def _scores(rows, capabilities):
    if (not isinstance(rows, tuple) or len(rows) != len(capabilities)
            or any(not isinstance(row, tuple) or len(row) != 3
                   or not isinstance(row[0], str)
                   or type(row[1]) is not int or type(row[2]) is not int
                   or not 0 <= row[1] <= row[2] or row[2] < 1 for row in rows)
            or tuple(row[0] for row in rows) != capabilities):
        _invalid("BAMF_TRANSLATED_SCORE_CENSUS_INVALID")
    return rows


def _verify_replay(record):
    expected_keys = {
        "schema_version", "task_sha256", "generation_digest", "source_binding_digest",
        "semantic_release", "rights_epoch", "correction_generation", "route", "dag_receipts",
        "costs", "outcome", "fallback_reason"}
    cost_keys = {"pure_operations", "reserved_operations", "operation_limit", "lookups",
                 "memo_hits", "backbone_calls", "local_refinements", "decoder_decisions"}
    if (not isinstance(record, dict) or set(record) != expected_keys
            or record["schema_version"] != SOLVE_REPLAY_SCHEMA
            or not all(_sha(record[key]) for key in (
                "task_sha256", "generation_digest", "source_binding_digest", "semantic_release"))
            or any(type(record[key]) is not int or record[key] < 0
                   for key in ("rights_epoch", "correction_generation"))
            or not isinstance(record["dag_receipts"], list) or not record["dag_receipts"]
            or not isinstance(record["costs"], dict) or set(record["costs"]) != cost_keys
            or not isinstance(record["outcome"], dict)
            or set(record["outcome"]) != {"type", "state", "sha256"}
            or not _sha(record["outcome"]["sha256"])
            or not isinstance(record["outcome"]["type"], str) or not record["outcome"]["type"]
            or (record["fallback_reason"] is not None
                and (not isinstance(record["fallback_reason"], str) or not record["fallback_reason"]))):
        _invalid("BAMF_HISTORICAL_SOLVER_REPLAY_INVALID")
    try:
        route = RouteKind(record["route"])
        state = ValueState(record["outcome"]["state"])
        receipts = tuple(DAGReceipt(**{
            **item,
            "selected_bindings": tuple((node, operator, tuple(refs))
                                       for node, operator, refs in item["selected_bindings"]),
            "executed_nodes": tuple(item["executed_nodes"]),
        }) for item in record["dag_receipts"])
    except (BilqisError, ValueError, TypeError, KeyError):
        _invalid("BAMF_HISTORICAL_DAG_REPLAY_INVALID")
    costs = record["costs"]
    if (any(type(value) is not int or value < 0
            for key, value in costs.items() if key != "decoder_decisions")
            or costs["decoder_decisions"] is not None
            or not 1 <= costs["operation_limit"] <= 64
            or costs["backbone_calls"] not in (0, 1)
            or costs["local_refinements"] > 64
            or costs["pure_operations"] + costs["reserved_operations"] > costs["operation_limit"]
            or costs["pure_operations"] != sum(item.operation_count for item in receipts)
            or costs["lookups"] != sum(item.lookup_count for item in receipts)
            or costs["memo_hits"] != sum(item.memo_hit_count for item in receipts)
            or any(item.source_binding_digest != record["source_binding_digest"]
                   or item.semantic_release != record["semantic_release"] for item in receipts)
            or (route is not RouteKind.UNRESOLVED and state is not ValueState.VALUE)
            or (route is RouteKind.UNRESOLVED and state is ValueState.VALUE)
            or (route is RouteKind.NEURAL_COMPOSITION and costs["backbone_calls"] != 1)
            or (route in (RouteKind.EXACT, RouteKind.CACHED_COMPOSITION)
                and costs["backbone_calls"] != 0)):
        _invalid("BAMF_HISTORICAL_SOLVER_REPLAY_COST_OR_SOURCE_DRIFT")


@dataclass(frozen=True)
class FrozenHistory:
    payload: bytes
    sha256: str

    def __post_init__(self):
        if (not isinstance(self.payload, bytes) or not _sha(self.sha256)
                or hashlib.sha256(self.payload).hexdigest() != self.sha256):
            _invalid("BAMF_HISTORICAL_BYTES_DRIFT")
        try:
            record = json.loads(self.payload)
        except (ValueError, UnicodeError):
            _invalid("BAMF_HISTORICAL_RECORD_INVALID")
        expected_fields = {
            "schema_version", "native_assessment_sha256", "generation_digest", "cohort_sha256",
            "rubric_sha256", "policy_sha256", "scope_sha256", "source_sha256", "source_family_ids",
            "capability_groups", "scores", "solver_contracts", "replay_records"}
        if (not isinstance(record, dict) or set(record) != expected_fields
                or record.get("schema_version") != HISTORY_SCHEMA
                or any(not _sha(record.get(key)) for key in (
                    "native_assessment_sha256", "generation_digest", "cohort_sha256",
                    "rubric_sha256", "scope_sha256", "source_sha256", "policy_sha256"))
                or not isinstance(record.get("capability_groups"), list)
                or any(not isinstance(pair, list) or len(pair) != 2
                       or not all(isinstance(value, str) and value for value in pair)
                       for pair in record["capability_groups"])
                or not isinstance(record.get("source_family_ids"), list)
                or not _names(tuple(record["source_family_ids"]))
                or not record["source_family_ids"]
                or not isinstance(record.get("scores"), list)
                or not isinstance(record.get("solver_contracts"), list)
                or any(not _sha(value) for value in record["solver_contracts"])
                or not isinstance(record.get("replay_records"), list)
                or not record["replay_records"]):
            _invalid("BAMF_HISTORICAL_RECORD_INVALID")
        capabilities = tuple(pair[0] for pair in record["capability_groups"])
        if not _names(capabilities) or not capabilities:
            _invalid("BAMF_HISTORICAL_CAPABILITY_CENSUS_INVALID")
        _scores(tuple(tuple(row) if isinstance(row, list) else row
                      for row in record["scores"]), capabilities)
        total = sum(row[2] for row in record["scores"])
        if (len(record["replay_records"]) != total or len(record["solver_contracts"]) != total
                or any(not isinstance(item, dict)
                       or item.get("generation_digest") != record["generation_digest"]
                       for item in record["replay_records"])):
            _invalid("BAMF_HISTORICAL_REPLAY_CENSUS_OR_GENERATION_DRIFT")
        for replay in record["replay_records"]:
            _verify_replay(replay)
        try:
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError):
            _invalid("BAMF_HISTORICAL_ENCODING_INVALID")
        if canonical != self.payload:
            _invalid("BAMF_HISTORICAL_ENCODING_NONCANONICAL")

    def record(self) -> dict:
        """Return a fresh decoded copy; original serialized bytes remain immutable."""
        return json.loads(self.payload)


def freeze_assessment(assessment: Assessment) -> FrozenHistory:
    if not isinstance(assessment, Assessment):
        _invalid("BAMF_HISTORICAL_ASSESSMENT_REQUIRED")
    cohort = assessment.cohort
    record = {
        "schema_version": HISTORY_SCHEMA,
        "native_assessment_sha256": assessment.digest(),
        "generation_digest": assessment.generation_digest,
        "cohort_sha256": cohort.expected_case_digest,
        "rubric_sha256": cohort.rubric_sha256,
        "policy_sha256": cohort.policy_sha256,
        "scope_sha256": cohort.scope_sha256,
        "source_sha256": cohort.source_sha256,
        "source_family_ids": sorted({case.source_family_id for case in cohort.cases}),
        "capability_groups": cohort.capability_groups,
        "scores": tuple((capability, *assessment.score(capability))
                        for capability, _ in cohort.capability_groups),
        "solver_contracts": assessment.solver_contracts,
        "replay_records": tuple(result.replay_record() for result in assessment.results),
    }
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return FrozenHistory(payload, hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True)
class TranslatorSpec:
    translator_id: str
    version: str
    implementation_sha256: str
    source_rubric_sha256: str
    destination_rubric_sha256: str
    source_policy_sha256: str
    destination_policy_sha256: str
    source_scope_sha256: str
    destination_scope_sha256: str
    source_family_ids: tuple[str, ...]
    destination_family_ids: tuple[str, ...]
    destination_capabilities: tuple[str, ...]
    uncertainty: str
    schema_version: str = TRANSLATOR_SCHEMA

    def __post_init__(self):
        if (not all(isinstance(value, str) and value for value in (
                self.translator_id, self.version, self.uncertainty))
                or not all(_sha(value) for value in (
                    self.implementation_sha256, self.source_rubric_sha256,
                    self.destination_rubric_sha256, self.source_policy_sha256,
                    self.destination_policy_sha256, self.source_scope_sha256,
                    self.destination_scope_sha256))
                or any(not _names(values) or not values for values in (
                    self.source_family_ids, self.destination_family_ids,
                    self.destination_capabilities))
                or self.schema_version != TRANSLATOR_SCHEMA):
            _invalid("BAMF_TRANSLATOR_SPEC_INVALID")


@dataclass(frozen=True)
class TranslationReceipt:
    source_history_sha256: str
    translator: TranslatorSpec
    scores: tuple[tuple[str, int, int], ...]
    receipt_sha256: str
    fresh_learning: bool = field(default=False, init=False)
    schema_version: str = field(default=TRANSLATION_SCHEMA, init=False)

    def __post_init__(self):
        if (not _sha(self.source_history_sha256)
                or not isinstance(self.translator, TranslatorSpec)):
            _invalid("BAMF_TRANSLATION_RECEIPT_INVALID")
        _scores(self.scores, self.translator.destination_capabilities)
        if self.receipt_sha256 != contract_digest({
                "schema": TRANSLATION_SCHEMA, "source": self.source_history_sha256,
                "translator": self.translator, "scores": self.scores,
                "fresh_learning": False}):
            _invalid("BAMF_TRANSLATION_RECEIPT_DRIFT")


def translate_history(history: FrozenHistory, spec: TranslatorSpec,
                      translator: Callable[[FrozenHistory], tuple]) -> TranslationReceipt:
    if (not isinstance(history, FrozenHistory) or not isinstance(spec, TranslatorSpec)
            or not callable(translator)):
        _invalid("BAMF_TRANSLATION_INPUT_INVALID")
    source = history.record()
    if (source["rubric_sha256"] != spec.source_rubric_sha256
            or source["policy_sha256"] != spec.source_policy_sha256
            or source["scope_sha256"] != spec.source_scope_sha256
            or tuple(source["source_family_ids"]) != spec.source_family_ids):
        _invalid("BAMF_TRANSLATOR_SOURCE_CONTRACT_DRIFT")
    try:
        translated = translator(history)
    except (BilqisError, ValueError, TypeError):
        _invalid("BAMF_TRANSLATOR_OUTPUT_REJECTED")
    scores = _scores(translated, spec.destination_capabilities)
    receipt_sha = contract_digest({
        "schema": TRANSLATION_SCHEMA, "source": history.sha256,
        "translator": spec, "scores": scores, "fresh_learning": False})
    return TranslationReceipt(history.sha256, spec, scores, receipt_sha)
