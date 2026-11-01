from __future__ import annotations

from bilqis_mlx.compatibility.identities import is_historical_capability
from .scores import _difference, _metric, _pp

def _soup(record):
    values=record.get("loss_last") or {}
    allocation=record.get("allocation") or {}
    total=sum(x for x in allocation.values() if type(x) is int)
    correct=values.get("trusted_soup_rows")
    coverage=(f"{100*correct/total:.1f}%" if total and isinstance(correct,int)
              else "-")
    return values,coverage



def _candidate_rows(record):
    grade=record.get("grade","?")
    attempts=record.get("attempt","?")
    numeric_before=record.get("numeric_before")
    numeric_after=record.get("numeric_after")
    bridge_before=record.get("bridge_before")
    bridge_after=record.get("bridge_after")
    bridge_confirm_before=record.get("bridge_confirm_before")
    bridge_confirm_after=record.get("bridge_confirm_after")
    old_before=record.get("old_before") or {}
    old_after=record.get("old_after") or {}
    old_change=_pp(sum(old_before.values())/len(old_before) if old_before else None,
                   sum(old_after.values())/len(old_after) if old_after else None)
    number=_difference(numeric_before,numeric_after)
    if is_historical_capability(grade) and grade in old_before:
        number=f"{100*old_before[grade]:.0f}>{100*old_after.get(grade,0):.0f}%"
    decision=record.get("decision","?")
    reason=record.get("reason","?")
    core={"grade":grade,"attempt":attempts,"strategy":record.get("policy_id","-")[:9],
          "method":record.get("instruction_method") or "-",
          "number":number,"bridge":_difference(bridge_before,bridge_after),
          "confirm":_difference(bridge_confirm_before,bridge_confirm_after),
          "old":old_change,"reward":_metric(record.get("reward")),
          "decision":f"{decision} {reason}"}
    sentinel_before=record.get("sentinel_before") or {}
    sentinel_after=record.get("sentinel_after") or {}
    worst=min((old_after[k]-v for k,v in old_before.items()),default=None)
    retention={"grade":grade,"attempt":attempts,
               "probe":_pp(old_before.get(grade),old_after.get(grade)),
               "worst":f"{100*worst:+.1f}" if worst is not None else "-",
               "sent":_pp(sentinel_before.get("accuracy"),sentinel_after.get("accuracy")),
               "ce":_metric_delta(sentinel_before,sentinel_after,"cross_entropy"),
               "prob":_metric_delta(sentinel_before,sentinel_after,"correct_probability"),
               "margin":_metric_delta(sentinel_before,sentinel_after,"margin")}
    soup,coverage=_soup(record)
    teaching={"grade":grade,"attempt":attempts,"soup":_metric(soup.get("soup_kl")),
              "cover":coverage,"sup":_metric(soup.get("supervised")),
              "parent":_metric(soup.get("parent_kl")),
              "credit":_metric(record.get("teacher_credit")),
              "bridge_ce":_metric_delta(bridge_before or {},bridge_after or {},"ce")}
    return core,retention,teaching



def _metric_delta(before,after,key):
    left,right=before.get(key),after.get(key)
    return _metric(right-left) if isinstance(left,(int,float)) and isinstance(
        right,(int,float)) else "-"
