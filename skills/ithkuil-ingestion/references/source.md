# Deterministic source stage

Use an explicit compatible project interpreter and repository/worktree root.
The repository's `lib/ithkuil/src/ingestion.py` owns orchestration. Run from that
repository root:

```sh
<python> -B -m lib.ithkuil.src.ingestion \
  --repo <absolute-repository> --python <absolute-python> --selection affix
```

`affix` is a bounded accepted-source rebuild. `all` selects the complete admitted
source corridor. Selection never changes semantic admission or invents a source
scope. Do not silently change the requested scope or select a different worktree.

Supply exact pinned raw sources and the accepted canonical CSV seed. Existing
published enrichment rows are retained inputs; no authenticated workbook or
training cache is a hidden prerequisite. The wrapper invokes existing source
owners, dataset validation and the frontier generator inside isolated staging.
It must not call semantic compilation after a source failure. It does not execute
RDF or graph operations in this stage.

Default execution is offline. Missing or mismatched snapshots block; restoration
must reproduce the accepted bytes, not silently replace manifest pins. Never use
`fetch_sources.py` snapshot main as recovery from a digest mismatch.

Inspect the normalized stage result for exact command identities/exits, validator
status, source-manifest digest, canonical artifact references, frontier receipt
and debt. Explicit parser debt remains visible. A successful bounded source stage
does not prove comprehensive New Ithkuil coverage or release qualification.

Reuse deterministic work only when its exact source/code/contract identities and
current artifact digests match. A typed failure preserves evidence and prevents
downstream mutation. If publication acknowledgment is ambiguous, reconcile the
native files and recorded expected digests before retry. Do not overwrite user
changes, guess a parser repair, or treat temporary output as published success.
