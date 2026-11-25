"""Observe the actual prepared native source and delivered adviser binding."""
from scripts.bamf.profiling.issue1645.reservation import require


def describe_delivery(prepared, mentor_record):
    from bilqis_mlx.runtime.atlas_training_contracts import _canonical_json_value
    from bilqis_mlx.runtime.source_execution import source_content_digest

    delivered = []
    for row, compiled in zip(prepared.training_batch.rows, prepared.compiled_rows, strict=True):
        meta = row.provenance
        require(len(compiled.sources) == 1, "diagnostic compiled source cardinality")
        source = compiled.sources[0]
        raw = source.source_row
        require(raw.get("id") == meta.row_id and raw.get("capability") == meta.capability_id,
                "diagnostic prepared row identity drift")
        observed_hash = source_content_digest((raw,))
        authoritative_hash = meta.source_row_content_sha256
        require(authoritative_hash is None or authoritative_hash == observed_hash,
                "diagnostic source digest drift")
        delivered.append({
            "row_id": meta.row_id, "capability_id": meta.capability_id,
            "source_id": meta.source_id, "source_family_id": meta.source_family_id,
            "episode_id": meta.episode_id, "optimizer_step_seed": meta.optimizer_step_seed,
            "source_seed": source.source_seed, "source_each": source.source_each,
            "observed_source_sha256": observed_hash,
            "authoritative_source_sha256": authoritative_hash,
            "target": _canonical_json_value(row.target),
            "native_target": _canonical_json_value(row.native_target),
            "gold": _canonical_json_value(raw.get("gold")),
            "role": meta.rehearsal or getattr(meta, "auxiliary_role", None) or "direct",
            "immediate_dependencies": (_canonical_json_value(meta.immediate_dependencies)
                                       if authoritative_hash is not None else None),
        })
    if mentor_record is not None:
        delivered_by_id = {item["row_id"]: item for item in delivered}
        require(len(delivered_by_id) == len(delivered), "ambiguous delivered mentor row")
        influences = {item["row_id"]: item for item in mentor_record["rows"]}
        require(set(influences) == set(delivered_by_id), "mentor delivery row mismatch")
        for row_id, item in influences.items():
            require(item["source_row_sha256"] == delivered_by_id[row_id]["observed_source_sha256"],
                    "mentor delivery source drift")
    return {"rows": delivered, "mentor_supervision": mentor_record,
            "mentor_supervision_status": "ABSENT" if mentor_record is None else "DELIVERED"}


def observe_native_call(original, captured):
    """Delegate once, record only supervision consumed by a successful call."""
    def execute(*args, **kwargs):
        result = original(*args, **kwargs)
        supervision = kwargs.get("mentor_supervision")
        require("mentor_supervision" not in captured, "multiple native gradient calls before capture")
        captured["mentor_supervision"] = None if supervision is None else supervision.to_record()
        return result
    return execute


def describe_perfect_target_skip(outcome):
    """Use the owner's preflight evidence without publishing a neutral event."""
    from bilqis_mlx.runtime.bamf_bundle.publication.preflight import (
        PERFECT_TARGET_SKIPPED, _evidence,
    )
    from bilqis_mlx.runtime.retention.local_preflight import require_preflight

    require(outcome.status == PERFECT_TARGET_SKIPPED, "unexpected un-intercepted outcome")
    preflight = outcome.preflight
    require_preflight(preflight)
    require(preflight.skip, "missing perfect-target skip authority")
    return {"status": outcome.status, "reason": PERFECT_TARGET_SKIPPED,
            "preflight": _evidence(preflight)}
