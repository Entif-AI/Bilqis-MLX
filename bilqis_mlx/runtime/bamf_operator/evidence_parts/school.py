"""Bounded observation of an already issued priority frontier and source offer."""
import json

from bilqis_mlx.runtime.lawful_teaching_frontier_contracts import (
    LawfulTeachingDisposition, LawfulTeachingFrontier,
)

SCHEMA = "bilqis.bamf.observed-school-frontier/v1"
MAX_SCHOOL_OBSERVATION_BYTES = 4096


def issued_school_observation(selection):
    """No authority reissuance, model work, source draws or candidate assessment."""
    frontier = getattr(selection, "_lawful_frontier", None)
    if type(frontier) is not LawfulTeachingFrontier:
        return None
    if len(frontier.capabilities) > 128:
        return None
    ready, held = [], []
    for row in frontier.capabilities:
        if row.disposition is LawfulTeachingDisposition.READY:
            ready.append(row.capability_id)
        elif row.disposition is not LawfulTeachingDisposition.EVIDENCE_COMPLETE:
            held.append(row.capability_id)
        if len(ready) + len(held) > 128:
            return None  # admission-only fallback, never a false complete frontier
    result = {
        "schema": SCHEMA,
        "run_id": frontier.run_id,
        "generation": frontier.accepted_generation,
        "manifest_sha256": frontier.accepted_manifest_sha256,
        "release_sha256": frontier.admitted_release_sha256,
        "frontier_sha256": frontier.frontier_sha256,
        "active_grade_sha256": frontier.active_grade_definition_sha256,
        "ready": ready, "held": held,
        "source_offer": None,
    }
    offer = selection.offer
    if offer is not None:
        result["source_offer"] = {
            "capability_id": offer.capability_id,
            "family_id": offer.source_family_id,
            "content_sha256": offer.source_authority.content_sha256,
        }
    from ..session_parts.evidence_mode import strict_mode_enabled
    if strict_mode_enabled():
        ranking = selection.ranking_evidence or {}
        result["salience_events"] = ranking.get("salience_events", ())
    if len(json.dumps(result, ensure_ascii=True).encode()) > MAX_SCHOOL_OBSERVATION_BYTES:
        return None
    return result
