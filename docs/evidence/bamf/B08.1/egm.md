# B08.1 independent EGM: source authority blocked

Reviewer: fresh-context Goldfish worker-17, read-only
Immutable reviewed code: `4225b2c7926b18ad918e7c2566104a4cbd4fbc21`
Prime affected tests: 77 total, 75 passed, 0 failed, 2 optional skips
Reviewer independently reran the affected suite and adversaries.

**Disposition: EGM_BLOCKED, one Blocker and one Major.**

## Blocker: caller-minted schema source authority

`atlas_engram_reads.py` introduced a local
`source:motif-schema:<schema-id>@<revision>` grant convention.
The reviewer reproduced a same-ID/revision schema with changed scope,
minted a matching `SourceGrant` and motif slot, and obtained an
unauthorized EXACT gather with a nonzero neural residual. The
canonical A03/A13 source-owner schema issuer is not consumed.
Recomputing a hash of a caller-provided schema does not prove the
schema is the released source contract. The B07.1 source-probe
authority blocker therefore propagates into B08.1.

## Major: incomplete cache dependency identity

The A13 `ApprovedContextProjection.digest` is returned as
`context_digests`, but the added schema-grant evidence and
revocation are not bound into that digest. The reviewer observed
the same context digest across a legitimate hit, schema-grant
revocation and forged-schema hit. It is not a sufficient cache
identity for motif reads. Accepted-generation/parameter provenance
must also be bound before any production cache consumes read results.

## Safe disposition and owner handoff

The numerical gate equation, exact/structural lookup, bitwise miss
behavior, two-site gradients and B07 parameter custody passed
independent review. **They are not source-admission evidence.**
After review, the public `read_motif` entrypoint was made
unconditionally fail-closed; the numerical proof was retained only
in an explicitly private experimental helper. Its tests now
include a public-entrypoint rejection (78 total, 76 passed, 2
optional skips). This mitigation prevents accidental runtime use
but does **not** clear the source-authority Blocker or establish
EGM PASS for B08.1.
This isolated branch is an experimental candidate only and must
not be merged or wired into a trainer while the Blocker remains.

Next authority step: A03/B07.1 must expose a source-owner-issued
released schema/typed-key witness that a B08 reader can verify
without accepting caller-minted grants. B08 must then bind the
verified schema, source/rights state and retained parameter
generation into its read-cache identity. Re-run the exact forged
same-ID/revision/scope adversary and a fresh independent EGM before
any integration.

No shared Lane B branch, unified trunk, live learner, source
admission, optimizer state or retained checkpoint was changed.
