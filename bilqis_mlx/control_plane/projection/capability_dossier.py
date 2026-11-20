"""Accepted-history projection for the existing CapabilityDossier contract."""
from bilqis_mlx.mission_control import CoverageState, DataValue, ValueState
from bilqis_mlx.mission_control.contracts.dossier import (
    CapabilityDossier, DossierEntry, DossierValue,
)

from ..native_contracts import data_value, missing_value, record_meta, run_ref


def _row(stats, capability):
    return stats.setdefault(capability, {
        "visits": 0, "retained": 0, "retained_ok": True,
    })


def _accepted_event(stats, native):
    capability = native.get("capability")
    if not isinstance(capability, str) or not capability:
        return
    row = _row(stats, capability)
    row["visits"] += 1
    outcome = native.get("how_outcome")
    retained = outcome.get("retained_steps") if isinstance(outcome, dict) else None
    if type(retained) is int and retained >= 0:
        row["retained"] += retained
    else:
        row["retained_ok"] = False
    scores = outcome.get("scores") if isinstance(outcome, dict) else None
    for score in scores if isinstance(scores, list) else ():
        if (not isinstance(score, (list, tuple)) or len(score) != 4
                or score[0] != capability or not all(type(item) is int for item in score[1:])):
            continue
        _cap, before, after, total = score
        if total <= 0 or not (0 <= before <= total and 0 <= after <= total):
            continue
        if row.get("total") not in (None, total):
            row["comparable"] = False
        row.setdefault("first", before)
        row["latest"], row["total"] = after, total
        row["top"] = max(row.get("top", before), before, after)
        row.setdefault("comparable", True)


def _accepted_health(stats, latest):
    health = latest.learning_health_state
    by_capability = health.get("by_capability") if isinstance(health, dict) else None
    for capability, evidence in (by_capability.items() if isinstance(by_capability, dict) else ()):
        if not isinstance(evidence, dict) or evidence.get("state") != "MEASURED":
            continue
        first, current, best = (evidence.get(name) for name in ("first", "latest", "best"))
        if not all(isinstance(item, dict) for item in (first, current, best)):
            continue
        totals = {item.get("total") for item in (first, current, best)}
        if len(totals) != 1 or next(iter(totals), 0) <= 0:
            continue
        _row(stats, capability).update(
            first=first.get("correct"), latest=current.get("correct"),
            top=best.get("correct"), total=current.get("total"), comparable=True,
        )


def accepted_capability_dossiers(history, rejected_records):
    """Return capability-scoped accepted facts without inventing missing metrics."""
    if not history:
        return ()
    latest, stats = history[-1], {}
    for generation in history:
        for native in generation.outbox:
            if native.get("event") == "BAMF_C16_3_ACCEPTED":
                _accepted_event(stats, native)
        visit = generation.teacher_state.get("last_visit")
        if isinstance(visit, dict):
            capability, strategy = visit.get("capability_id"), visit.get("policy_key")
            if isinstance(capability, str) and isinstance(strategy, str) and strategy:
                _row(stats, capability)["strategy"] = strategy
    _accepted_health(stats, latest)
    for record in rejected_records:
        capability = getattr(record, "capability_id", None)
        if capability and getattr(record, "state", None) == "REJECTED":
            _row(stats, capability)["visits"] += 1

    run, result = run_ref(latest), []
    ref = f"bamf-manifest:{latest.manifest_sha256}"
    unknown = DataValue(ValueState.UNKNOWN, None, None)
    for capability, row in sorted(stats.items()):
        if row.get("latest") is None and row["visits"] == 0:
            continue
        history_values = (
            DossierValue("was", data_value(row["first"])
                         if row.get("comparable") and row.get("first") is not None else missing_value()),
            DossierValue("visits", data_value(row["visits"])),
            DossierValue("retained_steps", data_value(row["retained"])
                         if row["retained_ok"] else missing_value()),
        )
        entries = [DossierEntry(
            f"accepted-history:{capability}", "performance", "accepted-history",
            "Accepted capability history", run.generation, 0,
            history_values, (ref,), None, None,
        )]
        if row.get("strategy"):
            entries.append(DossierEntry(
                f"accepted-strategy:{capability}", "teaching", "strategy",
                "Latest accepted teacher strategy", run.generation, 0,
                (DossierValue("strategy", data_value(row["strategy"])),),
                (ref,), None, None,
            ))
        result.append(CapabilityDossier(
            record_meta(
                f"dossier:{run.run_id}:{run.generation}:{capability}", run, latest,
                evidence_refs=(ref,), coverage=CoverageState.PARTIAL,
            ),
            capability, capability,
            data_value(row["latest"]) if row.get("latest") is not None else missing_value(),
            data_value(row["top"])
            if row.get("comparable") and row.get("top") is not None else missing_value(),
            data_value(row["total"]) if row.get("total") is not None else missing_value(),
            missing_value(), unknown, missing_value(), missing_value(), missing_value(),
            tuple(entries),
        ))
    return tuple(result)


__all__ = ("accepted_capability_dossiers",)
