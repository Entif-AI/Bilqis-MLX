---
name: ithkuil-ingestion
description: "Rebuild pinned New Ithkuil sources, compile canonical CSVs to RDF/SKOS, run conformance, inspect held/debt evidence and optionally materialize/read back an explicitly owned Falkor graph in Bilqis-MLX. Not curriculum admission or neural training."
---

# Ithkuil Ingestion

The graph stage is optional. Source and semantic builds require no graph service.

## Authority preflight

Resolve the explicit repository/worktree and Python interpreter. Read current
`AGENTS.md`, `lib/ithkuil/ingestion_contract.json` and applicable source profiles.
Use [references/authority.md](references/authority.md) for project governance,
publication posture or authority conflicts. Public-only access does not authorize
protected operations; stop and route unresolved protected requirements to their
owner. Surface conflicts rather than silently reconciling them.

## Rebuild pinned sources

Read [references/source.md](references/source.md), then invoke the repository's
`lib.ithkuil.src.ingestion` source action with explicit repository, interpreter and
source selection. It stages the existing canonical owners; do not copy parser
rules into a prompt or generate missing source rows. Default execution is offline.
Do not call the snapshot fetcher's main routine to fix a hash mismatch.

Return the normalized result, source-manifest identity, artifact references,
frontier receipt and explicit debt. A non-success result stops downstream work.
Read-only debt inspection reads existing receipts; do not invoke a publishing CLI
under an inspection request.

## Compile and check canonical CSVs

Read [references/semantic.md](references/semantic.md), then invoke the repository's
`lib.ithkuil.src.ingestion_semantic` action with explicit inputs and output root.
It calls the canonical compiler followed by every registered conformance gate.
Do not interpret rows, suppress failed gates or repair CSVs inside this action.
Surface both core and full-domain artifacts, their distinct digests, held ledger,
coverage and constituent gate evidence. Failed conformance blocks graph eligibility.

## Optional owned graph

Only for explicit graph-write intent, read [references/graph.md](references/graph.md)
and invoke `lib.ithkuil.src.ingestion_graph` with the successful semantic result and
exact target/readback parameters. Never infer a graph, reset permission or endpoint.
Return materialization and canonical readback evidence separately from semantic
success. A graph failure must not rewrite or invalidate the canonical corpus.

## Postflight and recovery

Validate the actual result and referenced artifact digests after action. Preserve
partial/held/debt status; source availability is not semantic or curriculum
admission. Use the run's typed failure and evidence for retry/reconciliation.
Never blindly replay an ambiguously acknowledged publication.

No curriculum/training/checkpoint/optimizer mutation, pin override, graph reset,
default graph fallback, Git push/merge or external publication is authorized by
this Skill. Graph writes require their own explicit target/owner authorization.
