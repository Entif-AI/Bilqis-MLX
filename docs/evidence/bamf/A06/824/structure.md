# #824 executable-release structural proof

Base: reviewed unified `06eb34d0435d2f41c6f3561cf8cad6988d5b849f`, synchronized
into Lane A and remotely verified. This bounded repair interrupts #785.
Specification: `docs/tasks/bamf-0.2/followups/EXECUTABLE_RELEASE_STRUCTURE_20261104.md`.

## Observed proof

The encounter checker reproduced two structural failures before extraction:
`executable_release.py` at 908 LoC and its companion test at 568 LoC.
The original focused suite passed 22/22. A public-module identity regression then
failed against the initial extraction and passed after preserving facade-owned
class/function/method identity. The final focused selection passes 23/23, with
no skips, including pickle roundtrip and facade monkeypatch behavior.

Existing definitions move into private owners for contracts, release manifests,
decoding, verification, source evidence, compilation and operations. Focused tests
follow catalog, lineage, manifest and public identity responsibilities. All moved
definitions compare equal by AST after undoing the facade qualification of global
lookups. Public late-bound lookups preserve existing patch points. All public
function/class/method type hints resolve after extraction.

A subprocess comparison against the original Git source produces identical
15,534 canonical manifest bytes and release digest
`792b131b0648cc296a191cee5c53d218de2dfc348ec56d21089ede8009781029`.
This is one fixed release fixture, not exhaustive source/learning qualification.

Reproduce focused behavior with:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/factory/tests/test_executable_release.py \
  bilqis_mlx/factory/tests/test_executable_release_catalog.py \
  bilqis_mlx/factory/tests/test_executable_release_lineage.py \
  bilqis_mlx/factory/tests/test_executable_release_manifest.py
python3 -B scripts/check_module_size.py --changed-from 06eb34d0
python3 -B scripts/quality/check_governance_integrity.py --base-ref 06eb34d0
```

Local detailed logs and the original-source comparison script are in
`.local/785-release-structure/`; they are execution artifacts, not required runtime
inputs. Final gate and independent-review receipts are reported at the exact
committed head on #824.

## Boundaries

No release schema, digest algorithm, source qualification, candidate/admission
policy, existing student, own AdamW, teacher, checkpoint or source asset changes.
Generated error documentation follows moved source locations only. The independent
external expected ABI fingerprint is unconfigured, so that check remains advisory.

#785 still needs admitted selection authority for the exact A03/schema/adapter
profile and predecessor. #420 still lacks aggregate actor/time/causal world-rule
qualification; #395 remains dependent on that breadth. This structural repair
neither closes those issues nor establishes neural learning. IPR-0220 remains
open; PM-2026-11-03-004 / RC-139 remains the source-selection incident.

## Round-one findings and deterministic repair

Pinned independent review of `77ae274d` found two Majors: stale generated error
inventory and an underspecified normative implementation plan. The error generator
had run before newly extracted files were staged. It scans Git-tracked paths;
no private-directory exclusion defect exists. The committed-tree check reproduced
`ERROR_FIELD_MANUAL_STALE` before repair. Stage-aware regeneration restores all
2,029 raw raises: original/candidate exception identity and multiplicity multisets
are exactly equal, with zero missing or added identities. The repaired check
reports zero new debt. No scanner rule or baseline changed.

The specification now names every created/modified owner, movement and facade
compatibility mechanics, ordered phases and concrete negative/positive checks.
These are mechanical/documentation repairs. Runtime source and tests remain
byte-identical to reviewed `77ae274d`; its 23/23 passing evidence is reused under
ADR-129. Incident `PM-2026-11-04-001` / `RC-144` is filed and natively read back
at canonical ledger Incidents row269; no new governance rule or pattern adopted.

Episode `A824-structure-20261104` remains round1/5. The initial FAIL is preserved;
resolution of its two scoped findings requires readback rather than resetting the
episode or claiming a new whole-candidate round.


Scoped resolution audit at `e855f408` closes both original Majors. The initial
FAIL is retained as history, with no new whole-review round. A documentation nit
about test ownership and unsupported test examples is corrected: the catalog test
owns identity/pickle and `_digest` patch behavior; lineage proof concerns release
geometry, not a claimed student/optimizer transaction. Final disposition is PASS
on the complete known finding set, with no unsettled Blocker/Major.
