# A05.5 source-visible atom semantic ABI handoff

- Issue: #594; parent A05 #357; Lane A
- Base: `ff2857c207d279526dc0f00c73682e296951fab9`
- Consumer: B11.1a #586 through the existing B02/B03 input path
- Disposition: `SOURCE_HELD`; no raw atom is embedding-ready
- Independent EGM: **PENDING**

## Source-authority finding

The live copular source adapter provides a real source-owned row-to-token law.
Its encoded source rows contain `ithkuil.op.COPULAR_IDENTITY` at an exact row
position and validate through the canonical registered adapter. The pinned A01
artifact maps that symbol to active ABI index 227 and semantic identity
`ithkuil:LEXSENSE-5286ade9db42c7/finite-reference-identity/v1`.

No current production source owner completes the next join. Production code
does not construct `StreamingAST` or `SourceAtom`. A13 source-row admission
issues frame and member grants, not a raw-atom `source_reference` tied to
`atom_evidence_digest`. A05 tests create raw-atom grants as fixtures, but a test
fixture is not source authority. Token spelling, ABI coincidence, or a
caller-created grant cannot fill this gap.

The implementation therefore does not create a `ConceptRef` for a raw atom.
The real copular/A01 witness is recorded as `SOURCE_HELD` until a source owner
defines the source-instance and raw-reference law.

## Implemented fail-closed handoff

`bilqis_mlx/semantics/source_atom_binding.py` defines the immutable A05-to-B02/B03
handoff without importing the source-adapter layer. The source-owned boundary in
`bilqis_mlx/source_adapters/atom_binding.py` reloads the registered A01 artifact,
reproduces the row with the canonical live source adapter, checks the exact row
token position against the A01 ABI, and rechecks current A13 rights. Each atom
record binds the source instance, atom index, token, source reference, A01
release and bundle, candidate semantic identity and ABI index, rights epoch,
correction generation, and a canonical digest.

Per-atom digests use the atom's own visibility boundary. Increasing the later
causal prefix does not change an earlier atom record. Source evidence or rights
changes do change the digest.

`revalidate_source_atom_handoff` rebuilds the record from source authority. It
does not trust a caller-pinned digest. `require_pinned_embedding_ready` is the
consumer guard for B02/B03. It refuses every current held or unmapped atom, so
the existing B03 raw-vector seam cannot treat an arbitrary 768-wide vector as
source-authenticated input.

## Executed evidence

The focused A05.5 suite passes **7/7** with the real pinned A01 artifact mounted.
It verifies:

- the canonical copular row reaches active A01 ABI index 227 but remains held;
- wrong token and shifted row-index mappings stay unmapped;
- changed raw references remain held even with a self-consistent fixture grant;
- revoked rights and stale correction state stay held and change the digest;
- forged ABI, type, release, bundle, duplicate, and future-position handoffs fail;
- earlier atom records remain byte-stable when the visible suffix grows; and
- the public B02/B03 consumer guard refuses the real held witness.

The adjacent A01/A05/A13/frame-adapter regression set passes **77**, with
**0 failures** and **1 existing optional real-corpus skip**.

The failing-before witness was the absence of
`bilqis_mlx.semantics.source_atom_binding`; the new focused test module failed at
import before the implementation existed.

## Remaining source-owner work

A source adapter must own the exact `StreamingAST`/`SourceAtom` construction and
raw `source_reference` grant, including its source-instance relation. That law
must preserve prefix stability and current A13 rights. Only then can A05.5 add a
`BOUND` path and let B02 derive differentiable raw-atom vectors from B01 identity
banks. B03 must then consume those source-bound vectors instead of arbitrary raw
atom matrices.

Until that source-owner change exists and passes independent EGM, #586 remains
blocked from claiming an authenticated h0 producer receipt through this seam.
No neural training, source promotion, shared Lane A merge, or B05 admission is
claimed here.
