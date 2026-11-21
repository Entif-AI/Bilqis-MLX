export default async function globalInteractionsJourney(page) {
  const check = (condition, message) => {
    if (!condition) throw new Error(message);
  };

  const reconnect = page.locator('[data-test-id="foundation-reconnect"]');
  if (await reconnect.count()) await reconnect.click();
  await page.locator('[data-test-id="nav-destination-school"]').click();
  const andCapability = page.locator('[data-test-id="school-matrix-capability-b-and"]');
  const notCapability = page.locator('[data-test-id="school-matrix-capability-b-not"]');
  await andCapability.waitFor();

  await andCapability.click();
  await page.locator('[data-test-id="investigation-inspector-compare-left"]').click();
  await notCapability.click();
  await page.locator('[data-test-id="investigation-inspector-compare-right"]').click();
  await page.locator('[data-test-id="investigation-compare-table"]').waitFor();

  await andCapability.hover();
  const highlighted = await page.evaluate(() => Array.from(
    document.querySelectorAll("[data-global-highlight]"),
  ).map((element) => [
    element.dataset.objectKind,
    element.dataset.objectId,
    element.dataset.globalHighlight,
  ]).filter((value, index, all) =>
    all.findIndex((candidate) => candidate.join("\u0000") === value.join("\u0000")) === index));
  check(JSON.stringify(highlighted.sort()) === JSON.stringify([
    ["capability", "B.AND", "selected"],
    ["capability", "B.IFF", "related"],
    ["capability", "B.NOT", "related"],
    ["capability", "B.OR", "related"],
  ].sort()), "only declared capability relations cross-highlight");

  await page.locator('[data-test-id="investigation-inspector-pin"]').click();
  await page.locator('[data-test-id="investigation-open-pins"]').click();
  await page.locator('[data-test-id="investigation-pin-open-0"]').waitFor();

  await page.locator('[data-test-id="investigation-inspector-note"]').click();
  await page.locator('[data-test-id="investigation-note-body"]').fill("GUI18 browser journey note.");
  await page.locator('[data-test-id="investigation-note-save"]').click();
  await page.locator('[data-test-id="investigation-note-0"]').waitFor();

  check((await page.locator('[data-test-id="investigation-posture-custody"]').innerText()).includes("FIXTURE_BACKED"),
    "global investigation posture identifies fixture-backed custody");
  check((await page.locator('[data-test-id="investigation-posture-mode"]').innerText()).includes("LIVE"),
    "global investigation posture identifies live mode separately from custody");
  check((await page.locator('[data-test-id="investigation-posture-authority"]').innerText()).includes("DERIVED"),
    "global investigation posture identifies derived authority");
  await page.locator('[data-test-id="investigation-open-authority"]').click();
  check((await page.locator('[data-test-id="investigation-authority-state"]').innerText()).includes("OWNER_ONLY"),
    "owner-only BAMF-0.2 remains the default authorization presentation");

  await page.locator('[data-test-id="investigation-open-saved"]').click();
  await page.locator('[data-test-id="investigation-saved-name"]').fill("Boolean capability triage");
  await page.locator('[data-test-id="investigation-saved-save"]').click();
  await page.locator('[data-test-id="investigation-saved-0"]').waitFor();
  check((await page.locator('[data-test-id="investigation-saved-0"]').innerText()).includes("non-authoritative"),
    "saved investigation is explicitly local and non-authoritative");

  await page.locator('[data-test-id="investigation-time-toggle"]').click();
  const generation = page.locator('[data-test-id="investigation-time-generation"]');
  await generation.evaluate((input) => {
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype, "value",
    ).set;
    setter.call(input, "44238");
    input.dispatchEvent(new Event("input", {bubbles: true}));
  });
  await generation.press("Enter");
  await page.waitForFunction(() => location.hash.includes("generation=44238") &&
    location.hash.includes("mode=HISTORICAL"));
  check(page.url().includes("generation=44238") && page.url().includes("mode=HISTORICAL"),
    "School preserves the exact historical lens");
  check((await page.locator('[data-test-id="investigation-posture-mode"]').innerText()).includes("HISTORICAL"),
    "global investigation posture exposes the historical lens explicitly");

  await page.locator('[data-test-id="nav-destination-memory"]').click();
  const memoryWorkspace = page.locator('[data-test-id="memory-workspace"]');
  await memoryWorkspace.waitFor();
  const memoryReceipts = page.locator('[data-test-id="memory-read-site-receipts"]');
  await memoryReceipts.evaluate((node) => {
    node.open = true;
    node.dispatchEvent(new Event("toggle", { bubbles: true }));
  });
  check((await memoryReceipts.innerText()).includes("motif-read:fixture:g44238:s0"),
    "Memory renders the exact historical motif identity");
  check(page.url().includes("generation=44238") && page.url().includes("mode=HISTORICAL"),
    "Memory uses the same historical lens");
  const savedInvestigation = page.locator('[data-test-id="investigation-saved-open-0"]');
  if (!await savedInvestigation.count()) {
    await page.locator('[data-test-id="investigation-open-saved"]').click();
  }
  await savedInvestigation.click();
  check(page.url().includes("generation=7") && page.url().includes("mode=HISTORICAL"),
    "saved live capture reopens as exact historical evidence after the lens changes");

  const liveFixtureUrl = new URL(page.url());
  liveFixtureUrl.hash = "";
  await page.goto(liveFixtureUrl.toString(), { waitUntil: "domcontentloaded" });
  const generationSummary = page.locator('[data-test-id="shell-generation-summary"]');
  await generationSummary.waitFor();
  check((await generationSummary.innerText()).includes("7"),
    "fresh fixture launch restores generation 7 in shell context");
  check((await page.locator('[data-test-id="investigation-posture-mode"]').innerText()).includes("LIVE"),
    "fresh fixture launch restores the live posture without production current authority");

  await page.locator('[data-test-id="nav-destination-learning"]').click();
  const learningForensics = page.locator('[data-test-id="learning-forensics"]');
  if (!await learningForensics.evaluate((node) => node.open)) {
    await learningForensics.evaluate((node) => {
      node.open = true;
      node.dispatchEvent(new Event("toggle", { bubbles: true }));
    });
  }
  await page.locator('[data-test-id="learning-candidate-inspect"]').click();
  await page.locator('[data-test-id="investigation-inspector-compare-left"]').click();
  await page.locator('[data-test-id="learning-episode-selector"]').selectOption(
    "episode-record:fixture:interference-reject",
  );
  if (!await learningForensics.evaluate((node) => node.open)) {
    await learningForensics.evaluate((node) => {
      node.open = true;
      node.dispatchEvent(new Event("toggle", { bubbles: true }));
    });
  }
  await page.locator('[data-test-id="learning-candidate-inspect"]').click();
  await page.locator('[data-test-id="investigation-inspector-compare-right"]').click();
  await page.locator('[data-test-id="investigation-compare-row-target-committed"]').waitFor();
  const candidateTable = await page.locator('[data-test-id="investigation-compare-table"]').innerText();
  check(candidateTable.includes("12/12") && candidateTable.includes("8/12"),
    "candidate compare keeps committed target values distinct");
  check(candidateTable.includes("Protected committed") &&
    candidateTable.includes("48/48"), "candidate compare keeps protected committed evidence");

  await page.locator('[data-test-id="nav-destination-lineage"]').click();
  await page.locator('[data-test-id="lineage-graph-generation-44238"]').click();
  await page.locator('[data-test-id="investigation-inspector-compare-left"]').click();
  await page.keyboard.press("Escape");
  await page.locator('[data-test-id="lineage-graph-generation-44240"]').click();
  await page.locator('[data-test-id="investigation-inspector-compare-right"]').click();
  await page.locator('[data-test-id="investigation-compare-row-topology-digest-version"]').waitFor();
  const generationTable = await page.locator('[data-test-id="investigation-compare-table"]').innerText();
  check(generationTable.includes("BAMF-V1") && generationTable.includes("BAMF-V2"),
    "generation compare exposes exact topology difference");
  check(generationTable.includes("recovered accepted checkpoint"),
    "generation compare preserves recovery disposition");

  const noPageOverflow = await page.evaluate(() =>
    document.documentElement.scrollWidth <= innerWidth);
  const tableOwnsOverflow = await page.evaluate(() => {
    const wrap = document.querySelector('[data-test-id="investigation-compare-table-wrap"]');
    if (!wrap) return false;
    const overflow = getComputedStyle(wrap).overflowX;
    return ["auto", "scroll"].includes(overflow) && wrap.scrollWidth >= wrap.clientWidth;
  });
  check(noPageOverflow, "investigation layout has no page-level horizontal overflow");
  check(tableOwnsOverflow, "compare table owns horizontal overflow inside its bounded container");

  return "GUI18_BROWSER_JOURNEY_PASS";
}
