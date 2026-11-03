# C02.1 / #713 source-authority checkpoint — 3 November 2026

Tested source: `10375fcc7f0b54bd3cf2e9ecad1820eb465fd76d`, pushed and read back
on `codex/bamf02-c-713-authority-20261103`. This branch starts at synchronized
Lane C `bcae1037` / reviewed unified `aa828eb5` and consumes the preserved
`10a41618` A06-manifest repair. No new runtime repair was authored in this turn.
The merge preserves accepted ADR-127 and regenerates operator error docs.

## Proof

With the existing real pinned A01 artifact supplied read-only:

- `scripts/run_tests.py bilqis_mlx/runtime/tests/batch`: **61/61**, no skips.
- Real source authority selection alone: **4/4**, no skips. The canonical fixture
  works; a source-valid alternate schema/artifact is rejected before model input.
- A06 feature IO and feature suites: **26/26**, no skips.
- Structure, governance, Factory architecture, docs and whitespace pass.
- Error control against exact reviewed unified reports zero new debt.
- Changed-file hygiene is **not green**: one new long-function finding at
  `bilqis_mlx/semantics/frame_compilation/prefix.py:114`, inherited from the
  preserved repair branch. Existing adapter findings remain separately reported.

## Ordinary independent review — unresolved source-authority gap

A fresh-context GPT-6.1 Terra High reviewer inspected the actual repair and source
receipts. This was ordinary independent review, not a new Google EGM round.

`feature_io_pins.py:67` and `atlas_feature_source_pins_v1.json:1` label the new
registry entry A06-attested. The cited A06.2 receipt describes generic immutable
export and a loader that consumes supplied expected identities. It does not
identify or authorize feature bundle
`0985051ad18344436185fa5b1bd38edc119ee08c082b441a32732dddd8a6693c`
or feature digest
`6ccdc67f2f5248493568c37941b55ec0cc6ab138f8a398ec5b800632733ae597`.
The fixture selects a union of three schema families and adapter bindings. The
reviewed evidence does not establish that this is the accepted source selection.

Hash pinning protects integrity and rejects alternatives after selection. It does
not prove source ownership of the selection. #713 therefore remains unresolved;
the original recorded source-authority defect is not closed. The A06 source owner
must provide an accepted artifact identity with a durable receipt, or a canonical
source-owned selection/derivation rule. C02 then consumes that authority and tests
canonical, forged and alternate-source-valid inputs. Successor predecessor custody
must remain fail-closed until accepted generation/checkpoint authority exists.

The review does not allege malicious artifact bytes or invalidate the observed
61/26 passing behavior. It identifies a missing source ownership seam. No current
#490 acceptance, aggregate EGM PASS, PR admission, neural admission or self-merge
is claimed. Full parent #490 review remains at its integrated candidate.

IPR-0220 remains opaque. No real student, own AdamW, teacher, checkpoint, source
release, graph or human-run state was mutated.
