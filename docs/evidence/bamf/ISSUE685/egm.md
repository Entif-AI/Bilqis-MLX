# Issue #685: restored admission proofs

Baseline: `0cac1a27abfb909b61646e5303ed40e9f60aa977`, synchronized from
reviewed unified into remote Lane C. Feature:
`codex/bamf02-c-685-admission-fixtures-20261101`.

## Observed failure and repair

Admission discovery failed with two import errors (19 discovered entries).
Direct prepared-successor/JIT/staging selection failed with three import errors.
The shared Factory fixture had moved, while three runtime test consumers still
referenced its former module. The repair imports the canonical existing fixture.
Production files and fixture behavior are unchanged.

Encountering the 648-line prepared-successor test required a structural
interruption. Work Stack `e47cd8d9-8137-474d-9bff-c4df8e87ae21` preserves the
original task. Its AST comparison proves identical bodies, signatures and
decorators for all twelve original test methods and seven fixture/helper methods,
plus the unchanged interruption exception. The five resulting owners contain
84, 147, 154, 130 and 176 lines. Native materialization, publication/replay,
topology and unchanged-geometry guards have separate cohesive test owners.

PM-2026-11-01-006 (public reproduction: [issue #685](https://github.com/Entif-AI/Bilqis-MLX/issues/685)) was filed and read back from the canonical native incident
ledger before repair. Existing relocation/affected-consumer proof controls apply.

## Executed proof

The commands in [the implementation plan](plan.md) passed:

- Atlas admission discovery: 25 tests.
- Prepared-successor, native materialization, publication/replay, topology,
  JIT and candidate staging: 24 tests.
- Fresh-process import of nine affected modules resolves the same canonical
  `CandidateStagingFixture` class from the relocated Factory owner.
- AST comparison retains all original tests/helpers and the exception.
- The repository file runner collects exactly the same 49 affected cases,
  with no tests added by imported fixtures.
- Changed-file structure/governance/smell, Factory architecture, docs, semantic
  boundaries, historical ABI and diff hygiene pass. Base-relative error control
  reports zero new debt; its inherited repository-wide inventory remains.

These are disposable engineering proofs. No real student, native AdamW,
teacher, admission release or checkpoint was modified. Full [C07 continuous source admission](https://github.com/Entif-AI/Bilqis-MLX/issues/380)
and BAMF retained-learning acceptance remain with their existing owners.

## Independent review

Google EGM pin: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
The fresh-context readiness reviewer read the pinned implementation-readiness
persona/standard and the plan. Its initial findings requested exact method
allocation, class/import names and proof commands. The plan supplies those
details; targeted re-audit returned PASS before implementation.

Fresh-context codebase-details review returned PASS, with no Blocker or Major.
The reviewer independently checked the original/staged AST, all twelve split
tests, fixture identity and repository-runner collection rules. Comprehension
review found two non-blocking documentation nits: incident locator and undefined
C07 owner. Public reproduction and owner links now resolve both. The reviewer
did not execute tests; the 25+24 executed results above belong to the implementer.
