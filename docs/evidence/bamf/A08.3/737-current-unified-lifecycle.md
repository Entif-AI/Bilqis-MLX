# #737 current-unified lifecycle refresh

This candidate resumes the preserved A08.3 lineage from reviewed feature head
`2c80599dfac07f3e5eaf5d82adf74411dc21b826` and merge-forwards reviewed unified
`aa828eb5cb8822a5614aa3353864bf187f83444d` into that lineage. The merge result
initially has the exact unified tree; it does not replay or duplicate the already
integrated #758 world-rule remediation.

The current qualified-world production files remain byte-identical to the final
reviewed #758 implementation where the applicable paths overlap. The integrated
authority boundary therefore remains deliberately narrow: `WORLD.IS_OCCURRED`
is the qualified world rule, using the typed `IS_OCCURRED(EventStatus)->Boolean`
identity and canonical source/provider authority. Unsupported world families
remain unqualified and fail closed rather than becoming caller-selected programs.

The merge-forward exposed one direct A08.3 lifecycle regression in current
unified. The school source owner had already been structurally split and the
finite-numeric provider now has implementation digest
`a52f346478852775053f07a79342e5a9e9266bc64a2df6fe953d6a64881c8b7d`, but
`compatibility/source_adapter_resume.py` had lost the exact one-way migration
from the prior provider digest
`2758cf678e9d2a45f3f5a1b5edd85d5ae513e54506c0d98853b9402b91572754`.
The existing provider-compatibility regression failed on the unmodified merged
tree. This candidate restores the same bounded migration rule that existed on the
reviewed A08.3 feature lineage: only the exact prior-to-modular implementation
pair is admitted, descriptor equality is otherwise required, and the existing
ADR-106 staircase migration may compose without admitting arbitrary provider,
profile, oracle, or reverse drift.

Focused current-tree verification after the repair:

- family binding/contracts/execution, semantic rule registry, stable world
  capability identity, world source authority, and numeric provider resume:
  **34/34 PASS, 0 skips**;
- the pre-repair current-unified lifecycle tree reproduced the provider-resume
  failure before the bounded compatibility restoration;
- the disposable verifier environment required `pyshacl` to load the existing
  SKOS-backed tests; installing it changed no repository dependency declaration.

The candidate mutates no learner, optimizer, teacher, champion, soup, accepted
checkpoint, or live training lineage. Final structure/governance/hygiene,
flow-control, hosted checks, and fresh pinned exact-head EGM are separate turn-in
gates and are not claimed by this intermediate receipt.
