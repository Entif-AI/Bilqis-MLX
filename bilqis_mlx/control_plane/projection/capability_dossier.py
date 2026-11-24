"""Accepted-history projection for the existing CapabilityDossier contract."""
import json
from dataclasses import asdict

from bilqis_mlx.mission_control import CoverageState, DataValue, ValueState
from bilqis_mlx.mission_control.contracts.dossier import (
    CapabilityDossier, DossierEntry, DossierValue,
)

from ..native_contracts import data_value, missing_value, record_meta, run_ref


SCORE_FIELD_COUNT = 4


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
        if (not isinstance(score, (list, tuple)) or len(score) != SCORE_FIELD_COUNT
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


def _release_entries(execution, run, release_ref):
    """Bound declared prerequisites and source adapter without inventing families."""
    if execution is None:
        return ()
    cap = execution.capability_id
    refs = (release_ref,)
    entries = (
        DossierEntry(
            f"source-binding:{cap}", "sources", "admitted-source-binding",
            "Admitted source binding", run.generation, 0,
            (DossierValue("provider_id", data_value(execution.provider_id)),
             DossierValue("source_anchor", data_value(execution.source_anchor)),
             DossierValue("oracle_id", data_value(execution.oracle_id)),
             DossierValue("provider_implementation_sha256",
                          data_value(execution.provider_implementation_sha256))),
            refs, "source", execution.source_anchor),
        DossierEntry(
            f"prerequisite-inventory:{cap}", "dependencies", "prerequisite-inventory",
            "Admitted prerequisite inventory", run.generation, 0,
            (DossierValue("prerequisite_count",
                          data_value(len(execution.prerequisites))),),
            refs, None, None),
        *(DossierEntry(
            f"prerequisite:{cap}:{dependency}", "dependencies", "prerequisite",
            "Admitted prerequisite", run.generation, 0, (),
            refs, "capability", dependency)
          for dependency in execution.prerequisites
          if len(f"prerequisite:{cap}:{dependency}") <= 512
          and len(dependency) <= 512),
    )
    # Reserve room for accepted-history and strategy entries; truncation is
    # observable through prerequisite_count and the partial dossier coverage.
    bounded, size = [], 0
    for entry in entries:
        cost = len(json.dumps(asdict(entry), ensure_ascii=True).encode()) + 1
        if len(bounded) >= 125 or size + cost > 32 * 1024:
            break
        bounded.append(entry)
        size += cost
    return tuple(bounded)


def _capability_dossier(latest, run, capability, row, execution, ref, release_ref):
    unknown = DataValue(ValueState.UNKNOWN, None, None)
    history_values = (
        DossierValue("was", data_value(row["first"])
                     if row.get("comparable") and row.get("first") is not None else missing_value()),
        DossierValue("visits", data_value(row["visits"])
                    if row["visits"] else missing_value()),
        DossierValue("retained_steps", data_value(row["retained"])
                     if row["visits"] and row["retained_ok"] else missing_value()),
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
    entries.extend(_release_entries(execution, run, release_ref))
    return CapabilityDossier(
        record_meta(
            f"dossier:{run.run_id}:{run.generation}:{capability}", run, latest,
            evidence_refs=(ref, release_ref) if execution is not None else (ref,),
            coverage=CoverageState.PARTIAL,
        ),
        capability, capability,
        data_value(row["latest"]) if row.get("latest") is not None else missing_value(),
        data_value(row["top"])
        if row.get("comparable") and row.get("top") is not None else missing_value(),
        data_value(row["total"]) if row.get("total") is not None else missing_value(),
        missing_value(), unknown, missing_value(), missing_value(),
        data_value("ADMITTED") if execution is not None else missing_value(),
        tuple(entries),
    )


def accepted_capability_dossiers(history, rejected_records, *, release=None):
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
    executions = ({item.capability_id: item for item in release.execution_plan.capabilities}
                  if release is not None else {})
    release_ref = f"factory-release:{release.release_sha256}" if release is not None else None
    for cap in executions:
        _row(stats, cap)
    ref = f"bamf-manifest:{latest.manifest_sha256}"
    for capability, row in sorted(stats.items()):
        execution = executions.get(capability)
        if row.get("latest") is None and row["visits"] == 0 and execution is None:
            continue
        result.append(_capability_dossier(latest, run, capability, row, execution, ref, release_ref))
    return tuple(result)


__all__ = ("accepted_capability_dossiers",)
