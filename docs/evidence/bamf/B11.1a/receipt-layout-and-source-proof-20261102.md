# B11 receipt layout and source-proof repairs — #747 / #748

Parent candidate: `ac89d382137e6581725d6f06220329e957fe0e7c` for #586.
Reviewed unified `2800946729e484875f7d1f57f0e6d85078936394` was already
ancestral at activation. Repairs use isolated branch
`codex/747-backbone-receipt-shape`; the parent remains parked pending consumption.

## Reproductions and repairs

For #747, the new layout selection initially failed with two failures and two
errors: same-byte rank-three reshaping was accepted, explicit dtype relabeling
was ignored by the receipt projection, and issued layout fields were absent.
The existing dtype guard already rejected actual float16 tensors; that did not
bind an explicit dtype label into provenance.

Repair `89682d8beca1bfec0e38b0c2a4d3a4d70e06bca1` derives `output_shape`
and `output_dtype` from actual h0/group replay outputs. Receipt projection v2
binds both alongside the existing content, source, parameter, generation, prefix,
cache, predecessor and motif evidence. Content validation compares the recorded
layout against the tensor. Issuance also checks execution-result shape/dtype
against replay. B05 continues to compute from owner replay, not receipt tensors.

Five regressions cover h0/group reconstruction and digest binding, same-byte
reshape rejection, dtype substitution, reshaped execution-result issuance and
recomputed self-consistent reshape receipts. The last witness asserts rejection
before selector numerical computation. A self-consistent evidence record still
does not become production execution authority.

For #748, the original ordered-group witness errored in the production source
qualifier with the real A01 artifact mounted. Supplying selection alone exposed
the same helper's invented source reference and unregistered frame. A complete
canonical frame also requires every member and its admitted feature schema.

Repair `3fefc026149ee8d6f87d0c577d002f945b4e3c87` replaces that invented
request with existing public-formal source projection, complete member requests,
the corresponding schema/role/source-binding feature manifest and matching
parameter extents. `DepthFrameFeatures` carries the actual `self.source.selection`.
No production source qualifier or fail-closed guard was weakened.

## Native proof

Executed on Apple Silicon with MLX/MLX Metal 0.32.4, NumPy 2.5.4, RDFLib 7.6.0,
pySHACL 0.40.2 and cryptography 50.0.2 in a fresh temporary virtual environment.
Supply the separately verified A01 artifact directory through
`BILQIS_A01_ATLAS_BUNDLE`; its bundle digest is
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`.
This repair did not regenerate or distribute that fixture.

```sh
python -B scripts/run_tests.py \
  bilqis_mlx.learning.source_atoms.tests.test_encoding \
  bilqis_mlx.learning.source_atoms.tests.test_backbone \
  bilqis_mlx.learning.source_atoms.tests.test_backbone_receipts \
  bilqis_mlx.learning.source_atoms.tests.test_backbone_formal_selection \
  bilqis_mlx.learning.source_atoms.tests.test_backbone_boundary_chaining \
  bilqis_mlx.learning.source_atoms.tests.test_backbone_receipt_layout \
  bilqis_mlx.runtime.tests.model.backbone.test_backbone_source_bridge
```

Result at repair source head `89682d8beca1bfec0e38b0c2a4d3a4d70e06bca1`:
`TEST_TOTALS total=35 passed=35 failed=0 skipped=0 errors=0` (643.731 seconds).
The dedicated #712 public-formal production negative/positive witness, stale
selected boundary, g2-as-g1, selected-state chaining, detached hidden/gradient
custody, parameter-tree isolation, generation/prefix/cache tampering and receipt
forgeries all executed. Original receipt selection: 16/16 passed.

All four changed Python files pass structure/hygiene checks with zero findings.
Factory architecture, governance and flow-control checks pass; error-control
reports `new debt 0`; whitespace is clean.

These are scoped remediation receipts, not a fresh EGM PASS. Parent #586 must
consume both repairs and satisfy its whole-candidate gates before the next pinned
EGM. No new PR, self-merge, durable student start/resume/stop, learner/AdamW,
teacher, admission, source release or graph mutation occurred.
