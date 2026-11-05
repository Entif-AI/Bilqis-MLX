# Executable Factory release structural repair

## Observed trigger and ownership

While tracing #785's existing Factory profile authority on reviewed unified
`06eb34d0435d2f41c6f3561cf8cad6988d5b849f`, the encounter checker reports
`executable_release.py` at 908 LoC and its companion test at 568 LoC. The
repository's mandatory structural interruption requires both owners and every
extracted companion to be below 240 LoC before selection work resumes.

Lane A owns the release-contract refactor and its tests. Keep the existing public
module, immutable record and callable identities, source/provider binding,
verification, predecessor checks, serialization and content digests. Factor
cohesive private owners and matching focused tests. Preserve public patch points
used by existing callers. Do not add profile selection or admission policy.

## Acceptance

- The public facade and every extracted implementation and companion test are
  below 240 LoC, with cohesive domain names rather than numbered file chunks.
- Existing focused release tests pass before and after extraction. Direct public
  identity, serialization/digest, tamper and predecessor checks remain covered.
- The import graph has no circular initialization failure. Existing release
  readers, compile/admit APIs and provider/answer verification remain usable.
- Source/ABI, changed-scope structure/governance/error/hygiene and independent
  pinned review pass before a ready PR to unified. Human integration is separate.

## Remaining source-selection boundary

A06 `build_feature_manifest(release, feature_schema)` validates the supplied
schema/role/adapter bindings. A03 pins authenticate the selected families; neither
chooses the set for an admitted Factory profile. The A06.2 receipt qualifies
immutable export/readback, not the later C02 fixture's three-family union.
#785 still requires an independently admitted profile/release/generation selector
naming those bindings and predecessor lineage. Hash pinning alone cannot grant
that authority. Multiple valid profiles must remain possible.

This structural repair does not close #785, #420, #395, #490 or the governing
IPR-0220 remediation. Source admission, accepted-generation custody and empirical
learning remain separate. Historical students, own AdamW, teacher, champions,
archives and the 100 GiB reserve remain untouched. Only the human initiates or
resumes actual student updates.
