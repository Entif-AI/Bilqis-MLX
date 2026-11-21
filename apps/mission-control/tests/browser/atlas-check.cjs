const { chromium } = require(process.env.BILQIS_PLAYWRIGHT_MODULE || 'playwright');
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const root = path.resolve(__dirname, '../../../..');
const { assetPathForRendererRequest } = require('../../electron/shell/renderer-protocol.cjs');
const server = http.createServer((req, res) => {
  if (req.url === '/apps/mission-control/renderer/atlas/atlas-fixture.mjs') {
    res.setHeader('Content-Type', 'text/javascript');
    res.end(fs.readFileSync(path.join(root, 'apps/mission-control/renderer/atlas/atlas-fixture.mjs')));
    return;
  }
  const prefix = '/apps/mission-control/renderer';
  const asset = req.url.startsWith(prefix + '/') ? assetPathForRendererRequest('bamf-mc://app' + req.url.slice(prefix.length), path.join(root, 'apps/mission-control/renderer')) : null;
  if (req.url !== '/' && !asset) { res.statusCode = 404; res.end(); return; }
  if (req.url === '/') {
    res.setHeader('Content-Type', 'text/html');
    res.end('<!doctype html><html lang="en"><head><title>Atlas fixture</title><link rel="stylesheet" href="/apps/mission-control/renderer/visual-tokens.css"><link rel="stylesheet" href="/apps/mission-control/renderer/components.css"><link id="atlas-css" rel="stylesheet" href="/apps/mission-control/renderer/atlas/semantic-atlas.css"></head><body style="display:block;padding:32px"><main data-test-id="fixture-host"></main></body></html>');
    return;
  }
  try { res.setHeader('Content-Type', asset.endsWith('.css') ? 'text/css' : 'text/javascript'); res.end(fs.readFileSync(asset)); } catch { res.statusCode = 404; res.end(); }
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  fs.mkdirSync('output/playwright/304', { recursive: true });
  const { atlasJourney } = await import(path.join(root, 'apps/mission-control/tests/browser/journeys/atlas-journey.mjs'));
  const result = await atlasJourney(page);
  const axePath = process.env.BILQIS_AXE_MODULE;
  if (axePath) await page.addScriptTag({ path: require.resolve(axePath) });
  result.variants = [];
  for (const [theme, density, width] of [['dark', 'comfortable', 1440], ['light', 'compact', 1440], ['dark', 'comfortable', 390], ['light', 'compact', 320]]) {
    await page.evaluate(([nextTheme, nextDensity]) => { document.documentElement.dataset.theme = nextTheme; document.documentElement.dataset.density = nextDensity; }, [theme, density]);
    await page.setViewportSize({ width, height: 1100 });
    const reflow = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth, width: document.documentElement.scrollWidth, viewport: innerWidth }));
    const overflow = reflow.overflow;
    if (overflow) throw new Error(`ATLAS_REFLOW:${width}:${JSON.stringify(reflow)}`);
    const violations = axePath ? await page.evaluate(async () => (await axe.run('[data-test-id="atlas-view"]', { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } })).violations.map(({ id, impact, nodes }) => ({ id, impact, count: nodes.length }))) : null;
    if (violations?.length) throw new Error(JSON.stringify(violations));
    result.variants.push({ theme, density, width, overflow, violations });
    await page.screenshot({ path: `output/playwright/304/atlas-${theme}-${density}-${width}.png`, fullPage: true });
  }
  result.projectionStates = [];
  await page.setViewportSize({ width: 1440, height: 1100 });
  const expectedStateText = {
    CURRENT: 'Current projection', STALE: 'Stale projection', PARTIAL: 'Partial projection',
    MISSING: 'Missing projection', ERROR: 'Evidence error',
  };
  for (const state of ['CURRENT', 'STALE', 'PARTIAL', 'MISSING', 'ERROR']) {
    const proof = await page.evaluate(async projectionState => {
      const atlas = await import('/apps/mission-control/renderer/atlas/semantic-atlas.mjs');
      const fixture = await import('/apps/mission-control/renderer/atlas/atlas-fixture.mjs');
      const api = fixture.createAtlasFixtureApi({ projectionState });
      const context = {
        runId: fixture.ATLAS_FIXTURE_IDENTITY.runId,
        generation: fixture.ATLAS_FIXTURE_IDENTITY.generation,
        semanticRelease: fixture.ATLAS_FIXTURE_IDENTITY.semanticRelease,
        mode: 'LIVE', fixture: true,
      };
      const overview = await atlas.loadAtlasOverview(api, context);
      document.querySelector('[data-test-id="fixture-host"]').innerHTML = atlas.renderAtlasMarkup({ status: 'ready', overview, context });
      const cockpit = document.querySelector('[data-test-id="atlas-release-cockpit"]');
      return { state: overview.projection.records[0].state, text: cockpit?.innerText || '' };
    }, state);
    if (proof.state !== state || !proof.text.includes(expectedStateText[state])) {
      throw new Error(`ATLAS_PROJECTION_STATE:${state}:${JSON.stringify(proof)}`);
    }
    result.projectionStates.push({ state, visible: true });
    await page.screenshot({ path: `output/playwright/304/projection-${state.toLowerCase()}.png`, fullPage: true });
  }
  await page.evaluate(async () => {
    const atlas = await import('/apps/mission-control/renderer/atlas/semantic-atlas.mjs');
    const fixture = await import('/apps/mission-control/renderer/atlas/atlas-fixture.mjs');
    const api = fixture.createAtlasFixtureApi();
    const context = { runId: fixture.ATLAS_FIXTURE_IDENTITY.runId, generation: fixture.ATLAS_FIXTURE_IDENTITY.generation, semanticRelease: fixture.ATLAS_FIXTURE_IDENTITY.semanticRelease, mode: 'LIVE', fixture: true };
    const overview = await atlas.loadAtlasOverview(api, context);
    document.querySelector('[data-test-id="fixture-host"]').innerHTML = atlas.renderAtlasMarkup({ status: 'ready', overview, context });
  });
  await page.evaluate(() => { document.documentElement.dir = 'rtl'; document.querySelector('[data-test-id="atlas-view"]').style.cssText = 'line-height:1.5;letter-spacing:.12em;word-spacing:.16em'; });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const spacingOverflow = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > innerWidth,
    width: document.documentElement.scrollWidth,
    viewport: innerWidth,
    offenders: [...document.querySelectorAll('[data-test-id^="atlas-"]')].map(element => {
      const rect = element.getBoundingClientRect();
      return { tag: element.tagName, className: element.className, testId: element.dataset.testId, left: rect.left, right: rect.right, width: rect.width };
    }).filter(item => item.left < -1 || item.right > innerWidth + 1).slice(0, 12),
  }));
  if (spacingOverflow.overflow) throw new Error(`ATLAS_RTL_TEXT_SPACING_REFLOW:${JSON.stringify(spacingOverflow)}`);
  result.rtlTextSpacingReducedMotion = true;
  await page.screenshot({ path: 'output/playwright/304/atlas-rtl-text-spacing-320.png', fullPage: true });
  fs.writeFileSync('output/playwright/304/browser-result.json', JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result));
  await browser.close(); server.close();
})().catch(error => { console.error(error); server.close(); process.exit(1); });
