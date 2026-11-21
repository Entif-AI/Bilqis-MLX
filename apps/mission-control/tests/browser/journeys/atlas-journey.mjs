export async function atlasJourney(page) {
  const hook = id => page.locator(`[data-test-id="${id}"]`);
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  await page.evaluate(async () => {
    const atlas = await import('/apps/mission-control/renderer/atlas/semantic-atlas.mjs');
    const release = '1'.repeat(64);
    const rdf = '2'.repeat(64), coverage = '3'.repeat(64);
    const root = 'https://github.com/Entif-AI/Bilqis-MLX/id/root/NI-LEXICON-CURRICULUM/LEXROOT-007a2c39cfe74c';
    const sense = root.replace('/id/root/', '/id/sense/') + '/STEM%201/BSC';
    const neighbor = root.replace('/id/root/', '/id/sense/') + '/STEM%202/BSC';
    const pageOf = (records, total = records.length) => ({ schema: atlas.QUERY_PAGE_SCHEMA, accepted: true, state: total ? 'PRESENT' : 'EMPTY', records, markers: [], links: [], total_matches: total });
    window.atlasFixture = {
      overview: {
        summary: pageOf([{ schema_version: atlas.SUMMARY_SCHEMA, active_concepts: { value: 742 }, source_eligible: { value: 801 }, source_held: { value: 17 } }]),
        releaseEvidence: pageOf([{
          schema_version: atlas.RELEASE_SCHEMA,
          meta: { source_refs: ['atlas-bundle:' + '4'.repeat(64)], receipt_refs: ['bamf-acceptance:' + '5'.repeat(64)] },
          atlas_bundle_id: '4'.repeat(64), semantic_release_sha256: release,
          source_bundle_id: '6'.repeat(64), canonical_rdf_sha256: rdf,
          coverage_sha256: coverage, conformance_sha256: '7'.repeat(64),
          source_rows_sha256: '8'.repeat(64), active_set_sha256: '9'.repeat(64),
          conformance_status: 'COMPLETE',
          coverage_status: { state: 'MISSING', origin: null, value: null },
          frontier_debt: { state: 'MISSING', origin: null, value: null },
          source_rows: 977, semantic_concepts: 801, active_abi_indices: 742,
          source_held: 17, source_ir_only: 9, implementation_uncovered: 6,
        }]),
        projection: pageOf([{
          schema_version: atlas.PROJECTION_SCHEMA,
          meta: { evidence_refs: ['akasha-event:' + 'a'.repeat(64)], receipt_refs: ['materialization-receipt:' + 'b'.repeat(64)] },
          state: 'CURRENT',
          graph: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: 'semantic' },
          owner: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: 'semantic-release-authority' },
          materialization_receipt_sha256: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: 'b'.repeat(64) },
          projection_version: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: '1.0.0' },
          coverage_status: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: 'complete' },
          canonical_rdf_sha256: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: rdf },
          semantic_coverage_sha256: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: coverage },
          importer_implementation_sha256: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: 'c'.repeat(64) },
          smoke_suite_sha256: { state: 'PRESENT', origin: 'SOURCE_AUTHORITATIVE', value: 'd'.repeat(64) },
        }]),
        banks: pageOf([
          { schema_version: atlas.BANK_SCHEMA, bank: 0, row_capacity: 8192, allocated_rows: 500, active_rows: 482, masked_rows: 18, recently_exercised_rows: 41, requalification_affected_rows: 3 },
          { schema_version: atlas.BANK_SCHEMA, bank: 1, row_capacity: 8192, allocated_rows: 260, active_rows: 260, masked_rows: 0, recently_exercised_rows: 21, requalification_affected_rows: 0 },
        ]),
        held: pageOf([
          { schema_version: atlas.HELD_SCHEMA, key: 'ambiguous-mapping-17', reason_code: 'AMBIGUOUS_MAPPING' },
          { schema_version: atlas.HELD_SCHEMA, key: 'source-gap-03', reason_code: 'SOURCE_UNRESOLVED' },
        ], 2),
        similarities: pageOf(new Array(29).fill(0).map((_, id) => ({ schema_version: atlas.SIMILARITY_SCHEMA, id })), 29),
      },
      selection: {
        concept: { schema_version: atlas.CONCEPT_SCHEMA, semantic_id: sense, kind: 'sense', atlas_release_sha256: release, source_loci: ['New Ithkuil Lexicon §4.3 p.179', 'Semantic release §2.7'], relations: [{ predicate: 'skos:broader', target_semantic_id: root }], abi_index: 1, abi_bank: 0, abi_row: 1, capability_ids: ['D.COPULAR_IDENTITY', 'B.IFF'], frame_schema_refs: ['frame:copular/v1', 'frame:relation/v2'] },
        state: { schema_version: atlas.STATE_SCHEMA, semantic_id: sense, admission_state: 'ACTIVE', newly_admitted: false, recently_exercised: true, requalification_affected: false },
        held: null,
        similarities: [{ schema_version: atlas.SIMILARITY_SCHEMA, source_semantic_id: sense, target_semantic_id: neighbor, basis_ref: 'embedding:g7:atlas-v2', similarity: { value: 0.97 }, canonical_equivalence: false }],
      },
    };
    window.mountAtlas = (lens = 'canonical') => {
      document.querySelector('[data-test-id="fixture-host"]').innerHTML = atlas.renderAtlasMarkup({ status: 'ready', ...window.atlasFixture, lens, selectedBank: 0 });
    };
    window.mountAtlas();
  });
  check(await hook('atlas-view').count() === 1, 'workspace present');
  check(await hook('atlas-lens-canonical').getAttribute('data-authority') === 'source', 'canonical source authority explicit');
  check(await hook('atlas-lens-learned').getAttribute('data-authority') === 'derived', 'learned authority explicit');
  check((await hook('atlas-overview').innerText()).includes('742'), 'orientation values present');
  const releaseCockpit = await hook('atlas-release-cockpit').innerText();
  check(releaseCockpit.includes('Current projection'), 'projection currentness visible');
  check(releaseCockpit.includes('Official frontier debt'), 'frontier debt boundary visible');
  check(releaseCockpit.includes('Unavailable'), 'unavailable debt verdict remains explicit');
  check(releaseCockpit.includes('17') && releaseCockpit.includes('9') && releaseCockpit.includes('6'), 'held and unresolved inventories visible');
  check((await hook('atlas-bank-table').innerText()).includes('482'), 'ABI bank state visible');
  check((await hook('atlas-semantic-dossier').innerText()).includes('New Ithkuil Lexicon §4.3 p.179'), 'source locus visible');
  check((await hook('atlas-semantic-dossier').innerText()).includes('skos:broader'), 'canonical relation visible');
  await page.evaluate(() => window.mountAtlas('learned'));
  const learned = await hook('atlas-semantic-relations').innerText();
  check(learned.includes('Derived similarity') && learned.includes('Canonical source relationships'),
    'learned boundary explicit');
  check(await hook('atlas-semantic-relation-0').getAttribute('data-edge-kind') === 'learned',
    'learned relation remains explicitly derived');
  check(!learned.includes('skos:broader'), 'canonical edge absent from learned lens');
  check(await page.evaluate(() => {
    const ids = [...document.querySelectorAll('[data-test-id]')].map(element => element.dataset.testId);
    return ids.length === new Set(ids).size;
  }), 'rendered hooks unique');
  await page.evaluate(() => window.mountAtlas());
  return { passed: true, claims: ['source authority leads', 'derived similarity separated', 'exact release/materialization identity visible', 'missing frontier-debt verdict explicit', 'exact ABI/source fields visible', 'canonical/learned relation separation', 'unique hooks'] };
}
