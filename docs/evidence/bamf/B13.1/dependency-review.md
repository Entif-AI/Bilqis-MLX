Lane C prerequisite qualification found four concrete Major gaps in the unpublished B13 candidate `dd6a68792df0cfcdd7eff1f9c0ca2d4a3cc53509`. A fresh isolated read-only reviewer inspected actual pinned EGM personas/standard, this issue and the bounded custody owners. This is preliminary code review, not completed feature EGM or source/model acceptance.

1. Tensor safetensors bytes are saved/hashed but not explicitly fsynced before the generation pointer, unlike the v1 save path.
2. Publication releases the pointer lock before outbox reconciliation, and cold load reconciles without it. The reused reconciler requires serialized observation+append; overlapping callers can duplicate journal delivery.
3. A successor can advance the pointer before reconciling its predecessor's pending outbox after a crash, stranding those committed predecessor events.
4. Sidecar checks accept missing compiler/bank identities and arbitrary schema strings. Complete versioned owner-record validation remains absent.

A separate repair branch `codex/bamf02-b13-478-custody-20261101` was cut from current Lane B `e73e9478` (contains unified `bb626d75`) and merged the exact same-Lane-B candidate. Original branch remains untouched. Lane C code was not given an unreviewed sibling-lane merge. Local structural/governance checks of the original candidate pass; native tests require MLX on the serialized M3 lane, so missing local MLX was not called a behavior failure.

I am reproducing and repairing the durability/outbox races with bounded disposable tests. Source-owned compiler/ABI schema qualification and real complete-model/learning acceptance remain explicit. No durable student start or self-merge.
