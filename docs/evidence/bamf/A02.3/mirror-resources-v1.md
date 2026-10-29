# A02.3 source-derived Registry mirror and bank resource candidate

Disposition: SCOPED_IMPLEMENTATION_EGM_PENDING. This is not the final
Registry export or A02.3/#401 integration closure.

The source-side mirror builder reloads A01's registered immutable
Atlas selection and replays the A02 allocation before deriving each
new row's semantic ID, exact global ABI index, bank/row, source status,
source record digest and source-attested SKOS.definition from the
verified canonical N-Triples. Formal ABI rows without a source
definition fail closed rather than inventing a description. The
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

## Independent EGM Major and source-definition repair

Goldfish worker-26 found that the first mirror candidate treated
SKOS.prefLabel as the Registry description. The existing Registry
contract uses that field for source-grounded semantic role/function,
and A01's frozen concept currently carries labels but drops the
original SKOS.definition. A label or empty string is not an
authoritative definition.

The mirror builder now requires the actual A01 source bundle path,
re-verifies its complete content-addressed manifest through A01's
existing source-bundle verifier, and binds its bundle ID to the
pinned frozen Atlas snapshot. It parses the verified canonical
N-Triples and derives description exclusively from the exact
SKOS.definition literals for the admitted semantic IRI. Multiple
definitions are preserved in deterministic order. Missing
definitions fail closed instead of fabricating meaning. The
source_record_digest binds both the frozen concept/formal binding
and the verified definitions.

The synthetic regression supplies a prefLabel deliberately different
from the definition, plus a definition-only source and missing
definition negative. The real A01 source-bundle witness also
passes. The Registry export owner still needs to persist/read back
this derivative; scoped EGM re-review remains pending.

Remaining owner work: integrate this derivative into the existing
Registry evidence/export contract, reconcile its actual persisted
readback and finish the complete admission/recovery proof.
