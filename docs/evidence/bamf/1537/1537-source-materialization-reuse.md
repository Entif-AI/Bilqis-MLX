# #1537 selected-source materialization reuse

Issue #1537 removes repeated selected-source preparation work without changing
teacher selection, neural execution, retention, or source-authority ownership.

The durable production-shaped baseline from #1518 measured selected-source
materialization at `10.020139375003055 s`. That historical witness predates
#1537's stage instrumentation, so its scalar cannot honestly be decomposed after
the fact. On exact implementation commit
`86cb2ae8dd27dcc74acfe5cefb345749c5084fe2`, a fresh neural-inert BAMF journey
measured a cold handoff of `0.314225 s` and exact warm handoffs of `0.131034 s`
and `0.150893 s`. The worst warm sample is about **66.41x faster** than the
#1518 baseline and is below both the `<=2 s` acceptance gate and the `<=1 s`
stretch target.

Warm samples performed zero Factory source-context rebuilds and zero compiled
model-source rebuilds.  The remaining warm cost is intentionally dominated by
fresh B11 authority/binding work (`0.108410 s` and `0.118425 s`). Both warm
samples report explicit selected-source wait time of `0.0 s` and exactly one
authenticated Atlas load for the visit, so selected-source reuse adds no second
Atlas reload. B11 bindings,
motif planning inputs, correction owners, registration, and currentness remain
visit-local instead of crossing the cache boundary.

The process-live cache is owned by `PriorityPlanningCache`, is capped at four
entries, and populates only after a complete successful preparation.  Its exact
identity binds accepted-generation, Factory-release, correction-frontier,
authenticated-feature, parent-candidate, source-row, provider implementation,
content, and episode identities.  Cache hits additionally re-resolve the
current registered source owner, compare callable-level owner identity, rebind
the row to the current registry/root/graph, and reissue the prepared B11 proof.
An interrupted cold build therefore cannot poison reuse, and a changed
process-live owner cannot inherit stale authority merely because provider hashes
still match.

The accepted candidate executor and Factory retention decision owners have an
empty #1537 diff against consumed main. The cross-offer regression additionally
locks identical rows, manifest, profile, source-row content, prepared model
sources, and prefixes across cold and warm materialization. Only the authority
and B11 wrappers that must be visit-local are reminted. Thus the optimization
does not introduce a new decision input or retention policy path; downstream
candidate and retention owners receive the same decision-visible prepared
content under the same accepted/source identities.

The reproducible witness is
`bilqis_mlx/runtime/tests/operator/pre_neural/test_source_materialization_reuse.py`
plus `scripts/bamf/profiling/source_materialization_reuse_profile.py`.  The
fixture creates a temporary accepted generation and data plane, performs no
optimizer update, and exercises the real `_execution_context` -> teacher
selection -> selected-source materialization path.
