# MC-GENERALIZED-1114 closeout

Issue: #1114 `BAMF-0.3 | Complete generalized Mission Control investigation UX and production polish`

## Scope closure

#1114 is a remainder/integration issue, not a greenfield GUI build. Current `main` carries the broad Mission Control surfaces delivered by GUI01-GUI20, the #1124 redesign program, #1128 global investigation recomposition, #1122 layout polish, and #1170 observed trainer telemetry. This closeout preserves those accepted surfaces and fills the generalized investigation gaps that remained after the owner-only BAMF-0.2 release boundary.

The implementation adds:

- local saved investigations that preserve exact run, generation, destination, selected identity, and comparison identities without becoming source or action authority;
- migration from the existing local operator-metadata v1 payload to v2 without discarding pins or annotations;
- an explicit global evidence posture that keeps live/historical mode, production/fixture custody, authority class, and coverage separate;
- a provider-neutral generalized authorization presentation contract whose presence can show principal, roles, inspection scopes, action scopes, lifecycle state, and authority-store reference;
- an owner-only fallback that is the unchanged BAMF-0.2 subset when no generalized authorization projection exists;
- an exact rule that a saved live investigation reopens as historical/read-only when its captured generation is no longer the verified current generation;
- a dedicated fixture-mode browser journey harness for global investigation behavior.

## Authority boundary

The authorization presentation is deliberately non-authorizing. Rendering a role or action scope never changes `mutationAvailable`, never bypasses CP05 preview/authorization, and never grants an operation. Existing control-plane preflight and accepted operator authority remain the effect boundary.

#1034 continues to own the generalized ordinary-user authority-store lifecycle. #1114 supplies the read-only presentation seam that #1034 can populate; it does not invent a second authority store, signer, permission database, or lifecycle protocol.

Saved investigations, pins, and notes remain UI-local operator metadata. Their schema explicitly marks saved investigations `OPERATOR_WORKSPACE_NON_AUTHORITATIVE`; annotations retain `OPERATOR_NOTE_NON_AUTHORITATIVE`.

## Acceptance mapping

1. **Provider-neutral contracts, not trainer internals.** Existing CP01-CP05 Mission Control contracts remain the provider boundary. The new authorization projection is a UI-facing contract independent of trainer implementation. Saved investigations contain only Mission Control view/context/object identities and local operator metadata.
2. **Historical/live posture unmistakable.** The investigation bar exposes mode independently from custody, authority, and coverage. Historical lens transitions continue to clear generation-dependent identities and disable mutation. Saved captures fall back to exact historical/read-only posture unless they still match verified live context.
3. **Generalized authorization composes with #1034.** The presentation contract accepts authority-store reference, principal, roles, inspection scopes, action scopes, and lifecycle state. Missing or malformed projection fails closed to the existing owner-only presentation and cannot create mutation authority.
4. **Measured/inferred/partial/fixture/unknown remain distinct.** `AuthorityClass`, `CoverageState`, fixture custody, live/historical mode, and freshness are not collapsed. The global investigation surface now renders the relevant posture explicitly.
5. **Owner-only GUI remains a clean subset.** With no generalized authorization projection and no saved investigations, existing owner flows render the same core destination/inspector/Operate behavior. Local metadata v1 migrates to v2 with an empty saved-investigation collection.

## Existing generalized surfaces retained

- exact global time lens and as-of historical navigation;
- literal compare with explicit incompatibility/unavailability;
- explicit cross-highlighting only for declared relationships;
- pinboard and non-authoritative annotations;
- exact deep links and inspector owner/evidence navigation;
- command palette and keyboard/focus handling;
- defensive offline/stale/progressive states and reconnect behavior;
- School, Capability, Learning, Atlas, Model, Memory, Teacher, SÍ SÉ SON, Corrections, Lineage, Resources, Evidence, and Operate workspaces;
- observed-versus-accepted trainer telemetry from #1170.

## Verification

Focused implementation proof:

```text
node --test apps/mission-control/tests/interactions/core.test.mjs \
  apps/mission-control/tests/interactions/metadata-and-compare.test.mjs \
  apps/mission-control/tests/shell-state.test.mjs
```

Result: 35 passed, 0 failed.

Mission Control renderer/domain suite:

```text
npm run bamf:test
```

Result: 483 passed, 0 failed after reverse-integrating `main` at `311c0c6753efda01d7d67155f1ac26be0aedf93b`.

The affected Electron security surface passed 68/68 tests on M3 Ultra when the unrelated `cp01-python-broker.test.cjs` file was excluded. The full security suite reached 71/73 Node tests; only the two CP01 broker subprocess tests failed because no installed M3 Python simultaneously provides the repository's modern syntax requirements and the `cryptography` package. Homebrew Python 3.14 lacks `cryptography`; system Python 3.9 lacks required modern standard-library/runtime features. The separate Python Electron-bridge unittest is blocked by the same M3 dependency split. No #1114 production file touches CP01. Hosted PR CI remains the final full-environment integration gate.

Browser journey:

```text
node apps/mission-control/tests/browser/global-interactions-check.cjs
```

Result on M3 Ultra: `GUI18_BROWSER_JOURNEY_PASS`.

This dedicated fixture-mode harness exercises compare, cross-highlighting, pins, notes, evidence posture, owner/generalized-authorization presentation, saved investigations, exact historical fallback, cross-view history, and bounded local overflow ownership. It preserves the fixture boundary that deliberately denies production verified-current authority.

Release structure checks:

```text
python3 -B scripts/check_module_size.py <changed Mission Control JS files>
python3 -B scripts/quality/check_governance_integrity.py --base-ref origin/main
git diff --check
```

Result: 0 module-size violations, 0 governance-integrity violations, and no whitespace errors. The generic history-walking `quality:structure` wrapper was stopped after it spent its time reconstructing ancestral merge scope rather than the 13-file PR diff; the same module-size contract was then run directly against the actual changed code paths.

## Deferred independently owned work

- #1034 remains the authority-store lifecycle owner.
- #1039 remains the extended soak/retained-learning program and may consume Mission Control telemetry without making this GUI issue its scientific owner.
- #1112 owns portable rejected/recovery history semantics rather than the investigation presentation itself.

No self-merge is authorized. Human review remains the merge gate.
