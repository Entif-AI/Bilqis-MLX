# B06 owner-trace interruption: cognitive solver — 3 November 2026

While tracing #810's missing production prediction owner, the delegated read-only
lookup encountered `runtime/cognitive_solver.py` at 494 lines and
`semantics/cognitive_dag.py` at 754 lines. The mandatory structural interruption
was activated before more feature work. The complete B06 objective, branch/head,
original #454 ancestry, dirty bytes, active tests, source fixtures, pending authority
questions and tracker work were preserved in the BIOS local Work Stack under
`.git/bamf-agent-state/ee89-810-20261103/`.

This first interruption splits only the solver. The already-encountered DAG owner
is the next single interruption after this one reaches a committed resumable state.
No recursive source-debt search was performed.

## Preserved behavior and identities

The public `runtime/cognitive_solver.py` is now a 40-line compatibility facade.
`runtime/_cognitive_solver/` owns contracts, results, policy and execution; each
module is below 240 lines. Focused tests mirror those owners under
`runtime/tests/capability/solver/`, with each companion below 240 lines. The
original facade has direct public identity/pickle tests.

Mechanical AST normalization proves all 13 original production definitions and
all 14 original test methods preserved. The extracted implementation resolves
historical module dependencies through the live public facade, using the same
public-facade resolver as the accepted C01 refactor. Public classes retain their
canonical module/pickle identities. The pre-existing executor-monkeypatch test
still passes; shared global dependencies are not frozen into copied bindings.
No route, budget, score, source, generation, cache or callback policy changed.

## Verification and limits

- Original behavioral selection: 14/14 pass.
- Mirrored selection plus two public identity tests: 16/16 pass, zero skips.
- The existing transitive import-boundary test fails before and after. Its exact
  72-name forbidden set is unchanged, not merely its count. Set fingerprint:
  `52ad1aa42c87c7c729669f59d64e22ebde0bcc124e6275596bade5510d699c60`.
- No baseline, exclusion, import guard or structural threshold was changed.

The preserved predicate failure remains a real C04 integration obligation. This
receipt establishes the bounded structural repair and behavior parity; it does
not claim green full-branch acceptance, production query authority, or #810/#736
completion. No fresh Goldfish round was spent on this mechanical repair.

The in-flight B06 affected native selection separately completed 100 tests:
99 passed, one failed, zero skips/errors. The failure is the existing learning
owner census (`36 != 32`), not a new neural or refinement failure. Its log and the
real-source forged-choice red/green receipts remain in the local Work Stack.
Those results do not establish final source/prediction/generation authority.

No actual student, optimizer update, teacher, checkpoint lineage, source, graph,
human-run or self-merge mutation was performed. IPR-0220 remains opaque.
