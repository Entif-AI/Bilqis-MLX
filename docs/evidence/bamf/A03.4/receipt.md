# A03.4 immutable released frame-schema body witness candidate

Issue: #578 (A03.4). Parent: A03 #349. Lane: A.
Consumed unified SHA: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`.
Source lane base: `9fa752b6410c8248aa784a361247a8a7230fb748`.
Review disposition: **EGM_PENDING**.

## Source and consumer contract

`bilqis_mlx/semantics/released_frame_schemas.py` freezes the *existing*
`FrameSchema.canonical_bytes()` and `SchemaTagMap` into a content-addressed
A03 release manifest. It binds semantic release, A01 Atlas bundle and source
bundle IDs, exact schema IDs/revisions, body digests and release-local map
identity. No new AST, schema semantics or parallel registry is introduced.

Issuance (`seal_released_frame_schemas`) stages source-owner bodies only;
staging is not an admission credential. `persist_released_frame_schemas`
uses an append-only digest-named artifact path and rejects altered existing
bytes. The consumer entrypoint (`load_released_frame_schemas`) requires the
**independently accepted A03 artifact digest**, a frozen A01 snapshot and,
where available, expected release/map pins. It verifies canonical manifest
bytes, body serialization, exact map coverage, A01 source identity and digest
before returning an offline witness lookup. A consumer must not derive its
trusted expected digest from the same untrusted candidate payload.

`VerifiedReleasedFrameSchemas.require_schema` refuses same-ID/revision body
substitution; `require_schema_bytes` canonicalizes JSON object key ordering
but preserves role-array order as semantic. These are suitable A03 gates for
B07 motif-key construction and B08 motif reads. A13 rights, revocation and
cache dependencies remain separate source-owner obligations.

## Focused verification

Initial red: new owner test module failed to import the absent A03.4 API.
After implementation:

- 8/8 new A03.4 tests pass, including one actual registered A source row;
- combined A03 schema/adapters, A04 codec and A03.4: 49 passed, 0 failed,
  1 optional real-Atlas skip;
- `git diff --check` passes;
- static module/error audits report no new A03.4 findings; inherited
  repository-wide findings remain outside this leaf.

The tests cover changed AST construct, role order, allowed types,
cardinality, scope, order mode, contract SHA, forged local catalog,
foreign release/map, A01 source-bundle mismatch, duplicate/noncanonical
manifest controls, append-only file drift and key-order canonicalization.

## Remaining source admission and downstream integration

This candidate supplies the versioned issuer/consumer mechanism, but does
not claim that an actual production A03 release manifest has been admitted
and pinned in a trusted source-owner release ledger. That publication must
be explicit and verified before B07/B08 treat a catalog as authority.
The B07.1/B08.1 consuming changes and their independent EGM remain separate
work. No neural admission, training or merge occurred.
