# Deterministic semantic build and conformance

Resolve the explicit CSV root and extraction-frontier receipt. A supplied source
stage result must be successful and match the requested closure; never continue
from a failed source stage. The CSV-only route needs accepted CSVs and frontier
evidence, not raw snapshots, a private workbook, a graph service or training state.

From the selected repository, invoke:

```sh
<python> -B -m lib.ithkuil.src.ingestion_semantic \
  --repo <absolute-repository> --python <absolute-python> \
  --input-root <absolute-csv-root> --frontier <absolute-frontier-json> \
  --output-root <absolute-dedicated-output>
```

Supply `--source-result <result-json>` when chaining a completed source action.
Use a dedicated generated-artifact location, outside inputs, compiler code and
protected runtime state. The output root must be new; retry into a fresh directory
and retain the failed run's evidence rather than overwriting it. Invoke the module
from the selected checkout, not an unrelated checkout's imported code.
The wrapper freezes the validated input closure and
invokes the contract's existing `skos.build` and `skos.conformance` commands.
It owns orchestration, not compiler or conformance semantics.

Keep the two artifact classes distinct. The core immutable generation contains
canonical RDF, digest metadata, input identity and held/error ledger. The full
conformance bundle contains independently built full-domain RDF, comparison,
coverage, source census, admitted mappings and each registered gate's evidence.
Their canonical digests need not be equal. A core generation alone is not an
importer-ready bundle.

Return the normalized result with command exits/logs, exact input/compiler/profile
identities, artifact paths/hashes, both canonical digests, held state, coverage and
conformance status. A failed build or gate is non-success; preserve diagnostics,
mark output non-materializable and route the named failure to its owner. Do not
change source rows, substitute old successful evidence or call a graph command.

Green conformance permits only eligibility for the separately authorized optional
graph stage. Partial source/semantic coverage stays partial. Neither success nor
graph eligibility grants release qualification, curriculum admission or training.
