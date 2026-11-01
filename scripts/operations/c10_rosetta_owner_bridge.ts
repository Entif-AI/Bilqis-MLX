// C-owned Observation adapter. Canonicalization and CID remain Rosetta-owned.
import { readFileSync } from 'node:fs';
import { buildTile, verifyTileIntegrity } from '@entif-ai/rosetta-core';
declare const __ROSETTA_SOURCE_REVISION__: string;
const request = JSON.parse(readFileSync(0, 'utf8'));
const fields = ['createdAt', 'observationId', 'owner_revision', 'schema', 'signal', 'source'];
if (Object.keys(request).sort().join('|') !== fields.sort().join('|') ||
    request.schema !== 'bilqis.c10.rosetta-observation-request/v1' ||
    request.owner_revision !== __ROSETTA_SOURCE_REVISION__ ||
    ['createdAt', 'observationId', 'signal', 'source'].some(key => typeof request[key] !== 'string' || !request[key]) ||
    new Date(request.createdAt).toISOString() !== request.createdAt) {
  throw new Error('Invalid C10 Observation request');
}
const tile = buildTile('rosetta.observation', {
  observationId: request.observationId, source: request.source, signal: request.signal
}, { pack: 'bilqis.bamf.c10', version: '0.1.0', parents: [], createdAt: request.createdAt });
const verified = verifyTileIntegrity(tile);
if (!verified.ok) throw new Error('Rosetta native integrity rejected');
process.stdout.write(JSON.stringify({ schema: 'bilqis.c10.rosetta-observation-response/v1',
  owner_revision: __ROSETTA_SOURCE_REVISION__, verified: verified.ok, tile }));
