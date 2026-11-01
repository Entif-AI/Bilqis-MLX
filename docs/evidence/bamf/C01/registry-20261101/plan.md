# C01 lossless registry expansion — readiness plan

Base Lane C/unified70e37ae2; same-C reviewed census65cd29af consumed.
Register all14 canonical late children and preserve exact live mirror bytes,
source hashes and original fuller repo specifications. Do not register duplicate
#587 or PR#636 as issue nodes. C14#559 is C14.4. Correct only the named parent
mirror drift/child lists and preserve original parent bytes/hashes in evidence.

Add versioned dependency_evidence metadata only to new entries. It contains
resolution(resolved|held), exact source_body_sha256 and clause_text,
external PR receipts, non-edge obligations and an unresolved explanation.
entry.deps is the reviewed set of known issue edges, not a settled empty list
when resolution is held. Preserve literal conditionals and historical producer
specifications separately; B11.1a must not acquire B05.4/final-B13 blocking edges.

New helper check_dependency_evidence(entry,body,issue_map) validates immutable
parsed results. Resolved state requires mechanically matching an explicit supported
prerequisite format: canonical linked section, literal short key list, same-parent
through range, or #635's explicit PR-plus-source-interface line. Unknown formats
cannot assert resolved. PR receipts remain PRs, never issue IDs. Source hash and
exact clause must match the mirror. Legacy canonical checks stay unchanged.

Held evidence retains known partial edges and unresolved receipt/conditional roles.
The validator reports identity/hash integrity separately from dependency resolution.
Any held contract makes overall status held, returns no execution order and exits
nonzero. Hard invalid data stays invalid. Thus registration cannot manufacture a
runnable or complete graph. The raw census still reports acknowledged duplicate587;
keep its verified resolution separately rather than suppressing it for a green audit.

Add mirrored helper tests and root-validator integration tests: lists/ranges,
foreign/duplicate keys, PR-versus-issue identity, source/clause tampering, unsupported
resolved prose, held partial/empty contracts and no execution order when held.
All171 canonical identities and exact mirror hashes must validate independently.
Full C01 reconciliation remains open while normalization holds remain. No body
rewrites, source admission, learner mutation or self-merge.

## Exact v1 contract and initial matrix

`reviewed-packets.json` pins all14 initial dispositions:5 resolved and9 held.
All33 referenced source snapshots are retained under sources/. They bind full
exact issue bodies, every differing fuller local specification, decisive owning
comments and verified PR metadata. duplicate-587.json retains the actual resolution
comment. A successful body parser must never override a reviewed held disposition.

Every new entry's dependency_evidence has exactly these keys:
`schema,resolution,body_sha256,clause,known_edges,external_receipts,source_records,obligations,unresolved`.
Schema is exactly `bilqis.bamf.dependency-evidence/v1`. resolution is resolved|held.
body_sha256 is lowercase64hex over exact UTF-8 body. clause is a nonempty exact
body substring. known_edges is a unique list of existing issue keys equal to deps.
obligations is a list of nonempty strings. unresolved is null for resolved and a
nonempty explanation for held. No status or empty list implies absent obligations.

source_records is a nonempty list of objects with exactly
`source_id,kind,locator,sha256,excerpt`. kind is body|spec|comment|pull_request.
source_id identifies a retained snapshot; locator records its original source.
sha256 must match the entire snapshot bytes and excerpt must occur in its UTF-8
text. The caller supplies `sources: Mapping[str,bytes]`; the helper does no I/O.
Snapshot filenames derive from validated source IDs, never arbitrary input paths.
The exact body must also match its body source record. All retained source records
must validate, including fuller specs and comment corrections; no optional skip.

external_receipts is a list of objects with exactly
`number,role,head_sha,merge_sha,url,source_id`. number is an exact positive int;
role is prerequisite|implementation; SHAs are lowercase40hex. The referenced
pull_request snapshot must have matching number,url,headRefOid,mergeCommit.oid and
state MERGED. Prerequisite and implementation roles stay distinct. For resolved
#635 only619,623,633,634 are prerequisites;636 is implementation. Receipt metadata
is source provenance, never runtime adoption permission or a replacement issue node.

`check_dependency_evidence(entry,body,issue_map,sources) -> EvidenceCheck` returns a
frozen dataclass `(status,known_edges,reason)`. status is EvidenceStatus enum:
INVALID,HELD,RESOLVED with wire values invalid,held,resolved. known_edges is a tuple.
INVALID reason is one of bad-record,source-drift,unknown-edge,bad-receipt,
unsupported-clause,clause-mismatch; HELD reason is the preserved unresolved text;
RESOLVED reason is null. INVALID returns no trusted edges. The root maps INVALID
to its existing typed MIRROR_DEPENDENCIES_MISMATCH diagnostic with evidence_reason.

Overall precedence: invalid > held > valid. `registry_integrity=valid` means all
existing hard schema/identity/hash/parent/map/known-edge/cycle checks and new evidence
shape/hash checks pass; it does not imply complete dependency meaning. Add
`dependency_resolution={status:resolved|held,held_keys:[sorted keys]}`. Any held
contract clears order and makes overall held. CLI exits0 only for valid,1 for held
or invalid. Hard-invalid inputs remain invalid. Legacy157 entries retain their
existing canonical linked-source enforcement and public compatibility.

Resolved grammar is strict: canonical linked section with exact key/issue/URL
mapping; short comma-separated key list; finite same-parent numeric through range;
or #635's literal merged-PR/qualified-receipt/source-interface prerequisite sentence.
Unknown or negated prose cannot assert resolved. Conditional C12, unnamed receipts,
additional local-spec obligations and historical producer context remain held in
the pinned matrix. This is census progress, not a smaller definition of C01 done.

## Pinned evidence and storage invariant

The helper additionally requires `sources['reviewed-packets']`, the frozen source
matrix bytes, and exact per-key equality of the entry's dependency_evidence with
that matrix. Changing only a held entry to resolved, clearing its unresolved text,
or removing specification/comment source records must reject. Matrix changes are
versioned source changes requiring independent review; this local consistency gate
does not cryptographically authenticate a self-rewritten matrix or grant runtime
admission. Canonical storage is `<manifest-directory>/dependency-evidence/` with
reviewed-packets.json and sources/<validated-source-id>.txt. The root adapter reads
only these fixed paths, refusing symlink/nonregular snapshot entries. No new CLI
option or arbitrary source path is introduced. validate_workstack gains an optional
backward-compatible evidence_sources mapping; legacy callers need no changes.
