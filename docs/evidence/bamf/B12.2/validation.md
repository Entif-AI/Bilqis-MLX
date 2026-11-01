# B12.2 validation

All neural checks below use disposable numerical tensors and native MLX 0.31.1.
No actual student, own AdamW, teacher, champion or run is modified.

- Original motif tests: 25 passed before extraction and 25 passed after.
  All 25 method ASTs, including decorators, occur once and remain identical.
- Initial candidate red: missing `atlas_candidate` module, one import error.
- Initial candidate green: eight passed, zero skips.
- Independent-review adversary red: eight passed, one failed because public
  construction did not raise `BilqisError`.
- Issuance repair green: nine passed, zero skips. Direct construction and
  `dataclasses.replace` optimizer/allocation forgery paths are rejected.
- Initial affected union: 44 passed, zero skips (eight candidate +25 motif
  +11 existing adapter/policy tests).
- Existing AdamW numerical/count/clipping cases: all 12 selected methods pass.
  The separate complete unbound-model allocation witness was deliberately not
  rerun; no constructor or topology source changed.
- Module size: zero violations against consumed unified.
- Governance integrity: zero violations against consumed unified.
- Changed-path code hygiene: passes without baseline expansion.
- Documentation check: passes.
- Whole architecture guard remains red at the existing unified
  `runtime/model_topology_v2.py:280 GENERIC_GRADE_IDENTITY_DISPATCH A,B` finding.
- Whole error-control guard remains red with 30 inherited findings in the
  unchanged scheduler/Factory owners. Shared-base repair PR #629 is open.
  No baseline, threshold or guard is modified by this issue branch.

Final repaired union: 45 passed, zero failures/skips (nine candidate +25
motif +11 adapter/policy). Targeted independent EGM re-review is scoped clear.
Commands are in `candidate-transaction-v1.md`.
