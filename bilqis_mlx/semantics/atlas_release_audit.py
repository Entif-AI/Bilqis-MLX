"""Public A12 source-authority audit and export-clearance facade."""
from ._atlas_release_audit import (
    AuthorityReceipt, ConsumerBinding, ExportClearanceReceipt,
    SOURCE_DISPOSITIONS, audit_atlas_authority,
    validate_export_clearance_context,
)

__all__ = (
    "AuthorityReceipt", "ConsumerBinding", "ExportClearanceReceipt",
    "SOURCE_DISPOSITIONS", "audit_atlas_authority",
    "validate_export_clearance_context",
)

# Preserve the historical public module identity after the structural split.
for _public in (
    AuthorityReceipt, ConsumerBinding, ExportClearanceReceipt,
    audit_atlas_authority, validate_export_clearance_context,
):
    _public.__module__ = __name__
