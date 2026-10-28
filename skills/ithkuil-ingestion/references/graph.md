# Optional owned graph and canonical readback

Graph operations are disabled unless explicitly requested. Require a successful
semantic result with green full-domain conformance, not just a core generation.
Partial coverage remains partial; green gates do not grant release qualification.

Use the repository's `lib.ithkuil.src.ingestion_graph` action. Supply the exact
semantic-result JSON, dedicated output location, configured host/port, graph name,
owner, smoke suite and readback tuple: notation lexical value, notation datatype
IRI and expected stable concept IRI. The bundle comes from the verified semantic
result. Never substitute another bundle, graph or endpoint after failure.

```sh
<python> -B -m lib.ithkuil.src.ingestion_graph \
  --repo <absolute-repository> --python <absolute-python> \
  --semantic-result <semantic-result-json> --output-root <dedicated-output> \
  --enable-graph --graph <exact-graph> --owner <exact-owner> \
  --host <configured-host> --port <configured-port> --suite <smoke-suite-json> \
  --notation <lexical-value> --datatype <notation-datatype-iri> \
  --expected-iri <stable-concept-iri>
```

Add `--required` only when graph completion is the requested outcome. Without
`--enable-graph`, the graph action is disabled and needs no database target.

The wrapper invokes the existing materialization-receipt and Akasha readback
owners. It introduces no graph semantic mapping. Source/CSV/RDF/conformance files
remain unchanged. Emit exact target, canonical digest, command exits/logs,
materialization receipt and readback status. Report graph-stage failure separately
from the still-valid semantic build; do not downgrade its evidence.

For an existing projection, surface the ownership/foreign-boundary dry-run and
whether a rebuild is required before mutation. A required reset is a blocker here:
no automatic reset, deletion or permission inference. Route it to separately
authorized reviewed reset handling. A foreign boundary is never a retry hint to
choose another graph.

Unavailable runtime is an explicit skip when graph work is optional. If graph
materialization is the required requested outcome, report that outcome blocked.
Do not provision a replacement service or silently run remote computation. Use
configured local execution; an existing operator-established tunnel may carry DB
traffic only. Never discover or copy credentials into logs or a Skill package.

Success requires validated materialization evidence and the required read-only
notation→concept→family/scheme/relation check against canonical RDF and receipt.
A connection, successful import exit or plausible lookup alone is not proof.
Keep semantic release, implementation, run, projection and receipt identities
distinct. No learner, factory/release, history or operational graph writes are
authorized by this semantic projection stage.
