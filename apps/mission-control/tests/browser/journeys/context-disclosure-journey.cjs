const assert = require("node:assert/strict");

const control = (page, id) => page.locator(`[data-test-id="${id}"]`);
const isOpen = (locator) => locator.evaluate((node) => node.open);
const settings = (page) => page.evaluate(() => ({
  theme: document.documentElement.dataset.theme,
  density: document.documentElement.dataset.density,
}));

async function pointerClick(locator) {
  await locator.scrollIntoViewIfNeeded();
  const hit = await locator.evaluate((node) => {
    const rect = node.getBoundingClientRect();
    const target = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
    return target === node || node.contains(target);
  });
  assert(hit, "intended control is not the pointer hit target");
  await locator.click();
}

async function contextDisclosureJourney(page, { capture = async () => {} } = {}) {
  const view = control(page, "shell-view-settings-disclosure");
  const system = control(page, "shell-system-context-disclosure");
  const viewTrigger = control(page, "shell-view-settings-trigger");
  const systemTrigger = control(page, "shell-system-context-trigger");
  const theme = control(page, "shell-theme-trigger");
  const density = control(page, "shell-density-trigger");
  const before = await settings(page);
  if (await isOpen(view)) await pointerClick(viewTrigger);
  if (await isOpen(system)) await pointerClick(systemTrigger);
  await pointerClick(systemTrigger);
  assert(await isOpen(system), "System Context did not open");
  await pointerClick(viewTrigger);
  assert(await isOpen(view), "View did not open");
  assert(!(await isOpen(system)), "System Context remained open");
  await capture("view-open");
  for (const panel of ["notes", "saved", "authority"]) {
    if (!(await isOpen(view))) await pointerClick(viewTrigger);
    const target = control(page, `investigation-open-${panel}`);
    await pointerClick(target);
    assert.equal(await target.getAttribute("aria-pressed"), "true", `${panel} did not activate`);
    assert(!(await isOpen(view)), `View survived ${panel} activation`);
    assert.deepEqual(await settings(page), before, "outside activation changed display preferences");
    await capture(panel);
  }
  await pointerClick(viewTrigger);
  await theme.focus();
  await page.keyboard.press("Escape");
  assert(!(await isOpen(view)), "Escape did not dismiss View");
  assert(await viewTrigger.evaluate(node => document.activeElement === node),
    "Escape did not restore summary focus");
  await capture("escape");
  await pointerClick(viewTrigger);
  await density.focus();
  await page.keyboard.press("Tab");
  assert(!(await isOpen(view)), "Tab out did not dismiss View");
  await pointerClick(viewTrigger);
  await pointerClick(control(page, "nav-destination-school"));
  assert(!(await isOpen(view)), "navigation left View open");
  assert.deepEqual(await settings(page), before);
  await capture("navigation");
  return before;
}

module.exports = { contextDisclosureJourney, pointerClick };
