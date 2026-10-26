# Bounded clean-room workflow

Issue #91 uses `lib/ithkuil/tests/fixtures/ingestion/descriptor.json`: two
UTF-8 excerpts of pinned New Ithkuil Chapter 3 tables T003/T035, plus a
mechanically selected, hash-bound canonical support closure from the recorded
repository commit. The support rows satisfy the current compiler's admitted
profile dependencies; they are existing inputs, not new extraction claims.
No VieDay material, model interpretation, private source, training state or
production source cache participates.

Run from the explicitly selected checkout with its compatible interpreter:

```sh
<python> -B -m lib.ithkuil.src.ingestion_fixture \
  --repo <repository> --python <python> \
  --descriptor <fixture-directory>/descriptor.json --output-root <new-output>
```

The repository runner binds excerpts to the existing `Builder` and
`extract_ch3_ca` owner. It extracts 52 atomic rows and the associated category,
composition, component, assertion and allomorph rows. Seed collisions must agree
exactly. The canonical relational preflight validates the resulting closure.
Then the existing semantic action runs core compilation and all four aggregate
conformance gates. The fixture contains real held/debt cases. Green conformance
with partial coverage is still partial coverage.

The fixture receipt is `bilqis.ithkuil.fixture-frontier/v1`, stored at
`sources/fixture_frontier.json`. Its scope and all three non-admission claims are
mandatory. It never overwrites or impersonates #86's `extraction_frontier.json`.
The semantic result carries `input_identity.fixture_only: true`.

For two completely independent runtime copies, run:

```sh
<python> -B -m lib.ithkuil.tests.ingestion_cleanroom \
  --repo <repository> --fixture <fixture-directory> --output-root <new-proof-root>
<python> -B -m unittest lib.ithkuil.tests.test_ingestion_cleanroom -v
```

Each copy contains only runtime code, profiles, required negative fixtures and
declared fixture inputs. It contains no production `_data`, `_raw`, Git checkout,
training state or generated cache. Source, every CSV, fixture receipt, held ledger,
canonical core/full RDF, coverage, conformance and content-derived manifests must
match exactly. `proof.json` lists the excluded workspace paths and identities
derived from those paths. No semantic field or timestamped artifact is silently
ignored.

Source pin/relational failures stop before semantic work. A deliberately extra
source-census row fails the real no-omission gate, suppressing graph eligibility.
Prior good artifacts remain byte-identical. Retry uses a new output directory outside the selected runtime checkout
and must reproduce the previous good content identity; no manual repair occurs.

The optional graph proof is `lib.ithkuil.tests.ingestion_graph_proof.prove_graphs`.
Use it only with explicitly resolved local tunnel host/port and isolated graph
write authority. It exercises the canonical graph CLI in each clean runtime,
compares materialization receipts excluding only graph name and timestamp,
injects an incorrect smoke expectation, retries with the original suite, and
proves foreign-data refusal without changing the node census or earlier evidence.
The fixture's frozen `smoke.json` uses real RDF identities; absent mappings and
neighbors are expected absences, not claims of mapping coverage. Graph fixtures
are isolated namespaces and are not a production graph release.

Dependencies: Python with repository `requirements-extraction.txt` and
`requirements-semantic.txt`; optional graph proof also needs
`requirements-falkor.txt` and an explicitly selected reachable service. The
fixture generator is an authoring tool requiring pinned production inputs; the
workflow never invokes it. Keep authoring and clean-room execution separate.
