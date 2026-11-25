"""Join the current disposable issued frontier to authenticated admission."""
from dataclasses import replace
import json

from bilqis_mlx.mission_control.contracts.model import (
    CoverageState, DataValue, ValueOrigin, ValueState, is_names, is_sha256,
)
from bilqis_mlx.mission_control.contracts.dossier import (
    CapabilityDossier, DossierEntry, DossierValue,
)
from bilqis_mlx.mission_control.contracts.snapshots import CurriculumFrontier, SchoolSnapshot
from .salience import observed_salience_records
from bilqis_mlx.runtime.bamf_operator.evidence_parts.school import (
    MAX_SCHOOL_OBSERVATION_BYTES, MAX_SOURCE_FAMILY_ID_LENGTH, SCHEMA,
)


class ObservedSchoolProjection:
    def __init__(self, records):
        self.admission = next((row for row in records
                               if type(row) is CurriculumFrontier), None)
        school = next((row for row in records if type(row) is SchoolSnapshot), None)
        self.admitted_count = school.capability_count.value if school is not None else None
        self.dossiers = {row.capability_id: row for row in records
                         if type(row) is CapabilityDossier}

    def project(self, observation, row):
        issued = row.get("school_frontier")
        admission = self.admission
        run = observation.meta.run
        if (admission is None or len(admission.admitted_capability_ids) != self.admitted_count
                or run != admission.meta.run
                or observation.connection_state != "LIVE"
                or not isinstance(issued, dict)
                or len(json.dumps(issued, ensure_ascii=True).encode()) > MAX_SCHOOL_OBSERVATION_BYTES
                or issued.get("schema") != SCHEMA
                or issued.get("run_id") != run.run_id
                or issued.get("generation") != run.generation
                or issued.get("manifest_sha256") != run.generation_manifest_sha256
                or issued.get("release_sha256") != run.factory_release_sha256
                or not is_sha256(issued.get("frontier_sha256"))
                or not is_sha256(issued.get("active_grade_sha256"))):
            return ()
        if any(type(issued.get(key)) is not list for key in ("ready", "held")):
            return ()
        ready, held = (tuple(issued[key]) for key in ("ready", "held"))
        if (not is_names(ready) or not is_names(held)
                or set(ready) & set(held)
                or not set(ready + held) <= set(admission.admitted_capability_ids)):
            return ()
        prefix = observation.meta.record_id
        frontier_ref = f"lawful-frontier:{issued['frontier_sha256']}"
        meta = replace(
            observation.meta, record_id=f"{prefix}:school",
            coverage=CoverageState.COMPLETE,
            evidence_refs=(frontier_ref, f"generated-grade:{issued['active_grade_sha256']}"),
        )
        frontier = CurriculumFrontier(
            meta, frontier_ref, ready, held, admission.admitted_capability_ids)
        dossier = self._source_offer(observation, issued.get("source_offer"))
        salience = observed_salience_records(observation, issued.get("salience_events"))
        return (frontier, *salience) if dossier is None else (frontier, dossier, *salience)

    def _source_offer(self, observation, offer):
        if not isinstance(offer, dict):
            return None
        capability = offer.get("capability_id")
        family = offer.get("family_id")
        content = offer.get("content_sha256")
        if (not isinstance(capability, str) or not isinstance(family, str)
                or not 0 < len(family) <= MAX_SOURCE_FAMILY_ID_LENGTH
                or not is_sha256(content)):
            return None
        dossier = self.dossiers.get(capability)
        if dossier is None or dossier.meta.run != observation.meta.run:
            return None
        ref = f"source-content:{content}"
        entry = DossierEntry(
            "observed-source-family", "sources", "observed-source-family",
            "Issued source family", observation.meta.run.generation,
            observation.meta.observed_at,
            (DossierValue("source_family_id",
                          DataValue(ValueState.PRESENT, ValueOrigin.MEASURED, family)),),
            (ref,), "source", family)
        meta = replace(
            observation.meta, record_id=f"{observation.meta.record_id}:dossier:{capability}",
            coverage=CoverageState.PARTIAL,
            evidence_refs=tuple(dict.fromkeys((*dossier.meta.evidence_refs, ref))),
            source_refs=tuple(dict.fromkeys((*observation.meta.source_refs, *dossier.meta.source_refs))),
            receipt_refs=dossier.meta.receipt_refs,
        )
        # The base dossier reserves capacity for this small observation.
        return replace(dossier, meta=meta, entries=(*dossier.entries, entry))
