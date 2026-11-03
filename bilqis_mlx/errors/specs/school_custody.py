"""Typed checkpoint custody errors with preserved historical wire identities."""
from .base import _spec


class CHECKPOINT_CUSTODY:
    MOTIF_SIDECAR_INVALID = _spec(
        ("SCHOOL", "CHECKPOINT_CUSTODY", "MOTIF_SIDECAR_INVALID"),
        owner="runtime.bamf_bundle.motif_codec", title="BAMF motif allocation sidecar invalid",
        message_template="BAMF motif allocation sidecar invalid.", disposition="PRESERVE_AND_INSPECT",
        next_action="Keep the retained generation; verify motif snapshot schema, keys, aliases and allocation digests before loading.",
        legacy_codes=("BAMF_MOTIF_SIDECAR_INVALID",),
    )
    OUTBOX_LINEAGE_DRIFT = _spec(
        ("SCHOOL", "CHECKPOINT_CUSTODY", "OUTBOX_LINEAGE_DRIFT"),
        owner="runtime.checkpoint_outbox", title="Checkpoint event outbox lineage drift",
        message_template="Checkpoint event outbox lineage drift.", disposition="PRESERVE_AND_INSPECT",
        next_action="Keep the current generation and journal; reconcile run, generation and exact event identities without rewriting history.",
        legacy_codes=("HUMAN_TRAINER_OUTBOX_LINEAGE_DRIFT",),
    )
    NUMERICAL_STATE_INVALID = _spec(
        ("SCHOOL", "CHECKPOINT_CUSTODY", "NUMERICAL_STATE_INVALID"),
        owner="runtime.mlx_checkpoint", title="BAMF numerical checkpoint state invalid",
        message_template="BAMF numerical checkpoint state invalid.", disposition="PRESERVE_AND_INSPECT",
        next_action="Keep the parent generation; inspect topology, extents, optimizer tree and exact optimizer step before saving.",
        legacy_codes=("BAMF_BUNDLE_NUMERICAL_STATE_INVALID",),
    )
    PARAMETER_IDENTITY_DRIFT = _spec(
        ("SCHOOL", "CHECKPOINT_CUSTODY", "PARAMETER_IDENTITY_DRIFT"),
        owner="runtime.mlx_checkpoint", title="BAMF checkpoint parameter identity drift",
        message_template="BAMF checkpoint parameter identity drift.", disposition="PRESERVE_AND_INSPECT",
        next_action="Preserve the bundle; compare parameter names and shapes with the bound topology and generation extents.",
        legacy_codes=("BAMF_BUNDLE_PARAMETER_IDENTITY_DRIFT",),
    )
    TENSOR_BINDING_INVALID = _spec(
        ("SCHOOL", "CHECKPOINT_CUSTODY", "TENSOR_BINDING_INVALID"),
        owner="runtime.mlx_checkpoint", title="BAMF tensor payload binding invalid",
        message_template="BAMF tensor payload binding invalid.", disposition="PRESERVE_AND_INSPECT",
        next_action="Preserve the bundle; inspect tensor schema, filename, topology and extent bindings before restoring arrays.",
        legacy_codes=("BAMF_BUNDLE_TENSOR_BINDING_INVALID",),
    )
    TENSOR_FILE_CORRUPTED = _spec(
        ("SCHOOL", "CHECKPOINT_CUSTODY", "TENSOR_FILE_CORRUPTED"),
        owner="runtime.mlx_checkpoint", title="BAMF tensor payload digest mismatch",
        message_template="BAMF tensor payload digest mismatch.", disposition="PRESERVE_AND_INSPECT",
        next_action="Do not load the payload; verify its bytes against the retained manifest and recover an intact immutable bundle.",
        legacy_codes=("BAMF_BUNDLE_TENSOR_FILE_CORRUPTED",),
    )
    MISSING_OR_EXTRA_TENSORS = _spec(
        ("SCHOOL", "CHECKPOINT_CUSTODY", "MISSING_OR_EXTRA_TENSORS"),
        owner="runtime.mlx_checkpoint", title="BAMF tensor census mismatch",
        message_template="BAMF tensor census mismatch.", disposition="PRESERVE_AND_INSPECT",
        next_action="Keep the retained generation; reconcile every weight, moment and update-count tensor with the declared parameter manifest.",
        legacy_codes=("BAMF_BUNDLE_MISSING_OR_EXTRA_TENSORS",),
    )
