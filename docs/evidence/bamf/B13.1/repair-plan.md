# B13.1 / #478 custody repair plan

Branch begins at Lane B e73e9478, consumes unified bb626d75, and reuses same-Lane-B
candidate dd6a6879 through a non-destructive merge. Original candidate is untouched.
No unreviewed sibling-lane source was merged into Lane C. Native checks use an
isolated M3 worktree, temporary data planes/run directories and one bounded MLX
process after a live writer-process census and nonblocking local lock.

## Reproduced and repaired storage/publication boundaries

Baseline dd6a6879: ten supplied native tests pass. New red checkpoint 522d2f7c:
three durability tests produce four failing assertions: missing tensor-file fsync,
publish/recovery overlap escapes the pointer lock, and successor advancement loses
the predecessor's pending event. Source checkpoint 8f76ee90 adds tensor fsync before
returning a payload binding, keeps publication/recovery/rejection reconciliation
under the same pointer lock, and reconciles a validated predecessor before advancing
its pointer. No source/curriculum/optimizer arithmetic change is made.

## Remaining sidecar Major

The unpublished writer currently accepts arbitrary fixture schema strings and
missing compiler/bank identities. Introduce explicitly B13-owned storage-envelope
schemas; these are NEW storage formats, not claims that A02/A12/B07 already issue
accepted production records. Additional JSON fields and values of the caller-supplied B13 envelope remain
preserved. Upstream serialized bytes/schema require a separately retained payload
or reference and remain outside this repair; never silently rename a real upstream
record schema. These wrappers do not claim upstream artifact byte fidelity.

Create `runtime/_custody/bamf_bundle/sidecar_contracts.py` owning schema constants
and `validate_identity_sidecars(extents,provenance,records,invalid)`; move only
identity-sidecar validation there from records.py. Keep records.py for manifest,
transition and complete candidate assembly. Create mirrored package-local
`test_sidecar_contracts.py`. Each new production/test module stays <240 lines.

Exact new schema values:
- semantic_abi: bilqis.mlx.bamf-semantic-abi/v1
- compiler_features: bilqis.mlx.bamf-compiler-features/v1
- correction_frontier: bilqis.mlx.bamf-correction-frontier/v1
- teacher_state: bilqis.mlx.bamf-teacher-state/v1
- evaluation_contract: bilqis.mlx.bamf-evaluation-contract/v1

Motif/plasticity keep their existing owner codecs/schemas; outbox retains its
existing event-lineage codec. Other five sidecars require exact new schema values.
Semantic ABI requires active_set_sha256==extents.active_semantic_digest,
semantic_bank_count exact int==extents.semantic_bank_count, and bank_identities a
list/tuple of exactly that many unique nonempty printable Unicode strings. IDs
remain opaque source-owned identities, not newly allocated banks or semantic IDs.
Compiler requires factor_map_sha256==extents.factor_map_digest and compiler_sha256
a lowercase SHA-256. Compiler rights_epoch/correction_generation must be exact
nonnegative ints. Correction epochs and teacher_epoch must also be exact nonnegative ints before
equality comparisons. Correction must carry the same epochs plus source_identity and
release_digest equal to provenance, and frontier as list/Mapping. Teacher identity
and epoch match provenance; next_seed is a nonnegative exact int. Evaluation
contract_sha256 is lowercase SHA-256. Additional owner fields remain preserved;
B13 validates its envelope and declared cross-bindings, not actual source admission.

Update only synthetic B13 fixtures to use the newly introduced envelope versions.
Add failing-before tests for every sidecar wrong/missing schema, missing/duplicate/
wrong-count/invalid bank identities, missing/malformed compiler digest, negative or
boolean epochs, and missing correction frontier. Confirm rejection before tensor
construction by loading a rehashed malformed sidecar/manifest in the codec path.
Positive native roundtrip still preserves all fixture metadata and optimizer state.

Run native codec/publication/durability/sidecar tests on M3, smallest affected
existing checkpoint/outbox tests, structure/governance/architecture/docs/error
checks, and diff check. Fresh pinned EGM readiness and implementation re-review
precede turn-in. Actual A02/B07/B12/B13 producer/full-model/source qualification,
retained-learning and genuine frozen-v1 witness remain explicit and unproven.
