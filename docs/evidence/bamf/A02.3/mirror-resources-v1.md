# A02.3 source-derived Registry mirror and bank resource candidate

Disposition: SCOPED_IMPLEMENTATION_EGM_PENDING. This is not the final
Registry export or A02.3/#401 integration closure.

The source-side mirror builder reloads A01's registered immutable
Atlas selection and replays the A02 allocation before deriving each
new row's semantic ID, exact global ABI index, bank/row, source status,
source record digest and source-attested preferred label. Formal ABI
rows without an attested concept carry an empty description and the
existing formal binding digest, never a fabricated meaning. The
mirror's active index set equals the staged tied-output domain; its
content digest is deterministic under admission input reordering.
The mirror is a derivative navigation/export delta, not a second
semantic authority.

The resource estimate uses the B01 complete parameter census and
accounts for FP32 weights plus both AdamW moment arrays. One added
8192x768 bank costs 75,497,472 bytes for these three arrays. The
lower bound for a complete staged checkpoint is combined with the
existing 100 GiB runtime reserve and an additional 30 GiB planning
allowance. The full-tree staging adapter refuses a caller-reported
insufficient budget before bank materialization. Actual publication
must remeasure free space at the existing checkpoint owner.

The package-local mirror and resource tests pass. The real A01 corpus
integration witness verifies a source-derived description and the
exact shared active set. No spreadsheet or Registry authority was
modified.

Remaining owner work: integrate this derivative into the existing
Registry evidence/export contract, reconcile its actual persisted
readback and finish the complete admission/recovery proof.
