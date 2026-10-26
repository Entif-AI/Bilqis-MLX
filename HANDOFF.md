# Issue #333 continuation | 2026-10-26

- Work: [#333](https://github.com/Entif-AI/Bilqis-MLX/issues/333),
  draft stacked [PR #335](https://github.com/Entif-AI/Bilqis-MLX/pull/335).
- Branch: `codex/333-factory-teacher-observations-20261026`.
- Verified implementation commit: `94a9e0301f16790c202058cd7ecd3af609f0c573`. Its predecessor is
  `d59b8ddf1fd58e3b72b9b20635a40b6a916809bc`.
- Base: `codex/320-model-topology-20261026`,
  `f09e44d35b5f544ef8d3e61ec127e326d0b09eb1`; PR #334 remains unmerged.
- Serialized writer: this continuation. Existing corrections were preserved.
- Authority: IPR-0220 remains OPEN. Protected location and current receipt belong
  in the protected checkpoint; this public projection uses only its opaque ID.
- Incident: PM-2026-10-26-003, RC-042, PAT-028; existing canonical incident enriched
  and read back. Earlier premature completion comment 6409512957 remains historical;
  correction 6409580404 holds until the superseding exact-head receipt is verified.

## Completed engineering and proof

Capture preserves valid skip before-scores while zero denominators and unscored
after/protected effects remain unmeasured. Cold readback now checks policy-epoch
and selection-source sidecars. Ordered duplicate rows, support composition,
topology/policy partitions and unchanged portable-v1 fixture remain covered.

Both ordinary and autonomy paths traverse retained/rejected/target-only/skip
outcomes with capture enabled and disabled. Disposable tests compare selection,
reward, RNG, source draws, batch order, learner, native AdamW and published bundle
identity. Actual visit events are committed through canonical outboxes, read before
journal emission and replayed twice with one logical observation and stable bytes.

- Focused current-Factory/native suite: 119 passed, 130 subtests.
- Portable workflow selection: 86 passed, no skips or errors.
- Architecture, closure, semantic boundaries, release/docs/error checks and module
  size ratchet pass. Smell baseline has no new findings after fixture decomposition.
- Historical ABI fingerprints match; external independent ABI enforcement remains
  advisory/unconfigured locally.
- Coverage map: `docs/operations/FACTORY_TEACHER_OBSERVATIONS.md`.

## Remaining boundary and next permitted action

Verify hosted CI and remote exact HEAD before posting the superseding #333 receipt.
That receipt clears only #324's observation-adapter prerequisite. #150 and #320
are still OPEN; #324 requires their verified completion plus its frozen workload,
policy/topology identities, evaluation seeds and finite budgets. No merge or real
qualification run is authorized by this handoff. Preserve the two-topology baseline
comparison and human-owned neural initiation. Actual learning remains NOT_MEASURED.

The real student, its native AdamW, teacher, original checkpoints, PR #290 and PR
#334 were not mutated. No `--human-run` was invoked. Do not resume historical
students or add Grade D/SKOS semantics as part of #333 closeout.
