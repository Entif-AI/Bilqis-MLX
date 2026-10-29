# A05 parent #357: source-visible compiler acceptance crosswalk

Status: **INDEPENDENT PARENT EGM PASS; integration receipt pending**.
This is a parent integration audit, not a new compiler
implementation or a neural-logit equivalence claim.

## Integration identity and prerequisites

- Reviewed unified: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`.
- Lane A audit base: `9fa752b6410c8248aa784a361247a8a7230fb748`;
  unified is already an ancestor, so no redundant merge.
- Original parent: A05 #357, children A05.1 #408,
  A05.2 #409, A05.3 #410. All three are CLOSED.
- The reviewed child code and its final independent EGM PASS
  are recorded in `docs/evidence/bamf/A05/egm.md`
  at immutable `de5bb9c`. The A03, A04 and A13
  source/codec/eligibility dependencies are present in
  reviewed unified. Their separate parent integration
  dispositions are not silently inherited.

## Original A05 acceptance crosswalk

| Original parent requirement | Executable witness |
| --- | --- |
| Compile every prefix of a literal four-member frame without leaking future members into embeddings/handles | `test_every_four_member_prefix_preserves_only_visible_atoms`, `test_future_frame_member_change_cannot_enter_prior_prefix` |
| At a fixed prediction prefix, future suffix changes cannot alter source-visible inputs, handles, masks, sidecars or cache identity | `test_future_suffix_does_not_change_prior_prefix_or_cache_key`, `test_invalid_future_frame_does_not_poison_earlier_prefix` |
| Incremental closure occurs only when required members are visible; old cache keys are never rewritten | `test_member_visible_later_moves_closure_without_rewriting_prefix`, `test_parent_cannot_close_while_child_is_future` |
| Mixed atomic, nested and packed source-visible sequences reconstruct the same visible AST | `test_nested_child_closes_before_parent_and_atomic_round_trips`, `test_exact_source_maps_role_access_expansion_and_prefix_ends` |
| Two unequal-length batch rows preserve row isolation and padding invisibility | `test_unequal_source_rows_have_separate_positions_and_cache_keys`, `test_padded_batch_rows_cannot_expose_other_row_or_future_content` |
| Hidden answer tensors never enter model inputs or their cache identity | `test_hidden_teacher_targets_are_not_model_input_or_cache_identity` |
| Enforce 1024 neural positions inclusively and reject overflow before packing/padding | `test_exact_1024_neural_positions_are_admitted`, `test_overflow_fails_before_packing_or_padding` |
| Split only at source-declared lawful boundaries, never truncate or mix source/policy/time frontiers | `test_lawful_source_boundaries_split_without_truncation` and A05.3's EGM source-boundary negatives |
| Raw atoms, frame closure and sidecars remain source-owned and byte-accurate | `test_first_admission_raw_atom_requires_source_owned_grant`, `test_revoked_frame_grant_blocks_closure_not_raw_atom_prefix`, `test_compact_frame_sidecar_matches_literal_canonical_wire_bytes` |
| Policy changes invalidate compiler identity | `test_policy_version_changes_compiler_digest_even_without_frames` |

The original parent explicitly delegates the final neural-logit
equivalence F05 witness to B11 #369 and C13 #385. This audit
does not claim that witness, actual MLX model-input parity,
retained learning, or live student custody. The source
compiler's pure causal boundary is the scoped A05 outcome.

## Executed evidence

On reviewed unified `7ad8f8a` with the pinned local test
environment:

- `scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_compiler.py`:
  **20 passed, 0 failed, 0 skipped**.
- Combined context, frame compiler and cognitive operators:
  **64 passed, 0 failed, 0 skipped**.
- The A05.1-.3 independent Goldfish leaf review at
  `de5bb9c` separately executed 20/20 owner and 83
  adjacent tests with one optional real-Atlas skip.

## Independent parent EGM disposition

Fresh-context Goldfish worker-12 independently reviewed
immutable Lane A `9fa752b` and unified `7ad8f8a`,
the original parent and all three closed child issues,
the reviewed `de5bb9c` code, the literal sidecar
fixture and source/EGM receipts. **A05 parent EGM PASS,
zero Blockers/Majors in A05-owned compiler scope.**

The reviewer independently reran 20/20 owner tests and
changed future token text, source references and
corresponding future grants at a fixed prediction prefix.
The compiled prefix and cache identity remained identical.
It verified byte-identical A05 source/tests/fixture
across the reviewed leaf head, Lane A and unified,
the inclusive 1024 boundary, independent padded rows,
hidden-answer isolation and nested/atomic round trips.

The required disposition remains
`COMPILER_PREFIX_PASS; NEURAL_F05_PENDING_B11`.
The independent review is not a B11/C13 F05 neural
logit proof, merge approval or learner-admission authority.
The parent issue can be considered for closure after
this receipt is durably integrated and the live GitHub
state is reconciled. No self-merge.
