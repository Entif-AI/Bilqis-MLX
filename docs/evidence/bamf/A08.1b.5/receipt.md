# A08.1b.5 Factory family integration candidate

- Issue: #557; parent A08.1b #418; Lane A
- Consumed unified: `9104ce733e04fb9c82420428b18dfdbf5db49535`
- Synchronized Lane A: `c18419b500216fb7e25a460ecc45aa1b522f3fb4`
- Learning state: `LEARNING_UNVERIFIED`
- Independent EGM: pending

## Owned integration

`skos_curriculum.registry` is behavior-only: it binds a constructive family to an
already-existing `CapabilityDefinition`, `ConstructionProgram`, and exact source
adapter/oracle. It never derives a capability ID from a semantic ID, family, source
row, operator, root, or grade; A08.2 retains stable capability/release identity.
Boolean and numeric formal behavior and the existing copular source fixture dispatch
by family/provider, not grade. Missing identity bindings remain
`IMPLEMENTATION_UNCOVERED`, preserving the complete A08.1a denominator and separate
source-held rows. A successful binding remains `LEARNING_UNVERIFIED`.

Source-backed positive-identity lessons now have an A03/A13 bridge. Exact tracked
CSV rows are verified against the canonical extraction frontier, preserve the full
A01 `(domain, table, key)` identity and row/file hashes, and are checked against the
pinned A01 concept before grants are issued. A03 visibility uses a source-local
atomic span; absolute CSV byte custody remains in the witness instead of being
misused as task causal-prefix coordinates. A13 frame/member grants are merged into
the current `SourceFrontier`; a revoked contrast grant conflicts on reissuance and
cannot be silently resurrected. The public Factory surface exports only the
A01-current lesson issuance/projection boundary, not the lower row-to-frame helper.

The constructive lesson compiler prefers a contrast from the same source-authority
class where possible, so a source-row positive identity is not paired with an ABI-only
contrast when a source-row contrast exists.

## Structural interruption

Repository governance required local structural remediation before #557 feature
work continued. The issue branch splits `factory/model.py` into focused lifecycle
owners, reduces root `scripts/` to 12 direct code files, and compartmentalizes the
90-file Ithkuil test root into source/semantic subdirectories. Oversized notation,
mapping, and SKOS-policy modules/tests were split below the required limits. Broad
moved semantic suites passed 464/464; focused split suites passed 93/93; structure
and governance checks report zero violations.

## Focused proof

Current #557 suites pass 31/31 before final EGM, covering family/grade-neutral
binding, missing constructor, wrong oracle/checker authority, preserved denominator,
no learning-credit promotion, source-row byte identity, exact A01 source identity,
source-local prefix semantics, frame/member grant requirements, contrast-only
revocation, and rejection of ABI/relation attempts to mint source-row provenance.

No neural update, capability admission, A08.2 identity allocation, or self-merge is
claimed.
