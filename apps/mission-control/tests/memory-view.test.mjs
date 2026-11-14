import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  MEMORY_FIXTURE_CONTRACT,
  MEMORY_GENERATIONS,
  REJECTED_MEMORY_CANDIDATE,
} from "../renderer/memory/memory-fixture.mjs";
import {
  capabilityInterpretation,
  currentMemoryGeneration,
  memoryCompare,
  memoryDeepLink,
  pageSummaries,
  priorMemoryGeneration,
  receiptTotals,
  rejectedCandidateInvariant,
  slotAddress,
  slotHitRate,
  stableMemoryIdentity,
} from "../renderer/memory/memory-model.mjs";
import { parseDeepLink } from "../renderer/deep-link.mjs";
import { INSPECTOR_OWNERS } from "../renderer/shell-state.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");
const rendererRoot = path.resolve(here, "../renderer");

test("summary reconciles literal hit miss and gate counts from fixture receipts", () => {
  const current = currentMemoryGeneration();
  const totals = receiptTotals(current);
  assert.deepEqual(totals, {
    exact: 14,
    structural: 6,
    misses: 5,
    hits: 20,
    reads: 25,
    hitRate: 0.8,
    gateEligibleHits: 20,
    gateUses: 13,
    gateUseRate: 0.65,
  });
  assert.equal(current.readReceipts.reduce((n, row) => n + row.exactCount + row.structuralCount, 0), totals.hits);
  assert.equal(current.gateReceipts.reduce((n, row) => n + row.usedHits, 0), totals.gateUses);
});

test("fixture geometry matches executable motif page and telemetry contracts", () => {
  const identitySource = fs.readFileSync(
    path.join(repoRoot, "bilqis_mlx/learning/_engram/atlas_engram_identity.py"), "utf8",
  );
  const reportSource = fs.readFileSync(
    path.join(repoRoot, "bilqis_mlx/learning/atlas_engram.py"), "utf8",
  );
  assert.equal(MEMORY_FIXTURE_CONTRACT.pageRows, 16_384);
  assert.equal(MEMORY_FIXTURE_CONTRACT.vectorWidth, 128);
  assert.equal(MEMORY_FIXTURE_CONTRACT.stateBytesPerPage, 25_165_824);
  assert.match(identitySource, /INITIAL_MOTIF_CAPACITY, MOTIF_VECTOR_WIDTH = MOTIF_PAGE_SHAPE/);
  assert.match(identitySource, /MOTIF_PAGE_STATE_BYTES = INITIAL_MOTIF_CAPACITY \* MOTIF_VECTOR_WIDTH \* 4 \* 3/);
  assert.match(reportSource, /class MotifReadReport/);
  assert.match(reportSource, /HELD, foreign-release, and quarantined outcomes are non-reads/);
});

test("atlas aggregates by page but drill-down resolves exact stable BAMF memory identity", () => {
  const current = currentMemoryGeneration();
  const pages = pageSummaries(current);
  assert.deepEqual(pages, [{
    pageIndex: 0,
    capacity: 16_384,
    allocated: 5,
    active: 4,
    held: 1,
    optimizerParticipating: 4,
  }]);
  const slot = current.slots[0];
  const identity = stableMemoryIdentity(slot);
  assert.equal(identity, slot.keyDigest);
  assert.equal(slotAddress(slot), "motif.page.0[0]");
  assert.equal(identity.includes("motif.page.0"), false);
  assert.equal(identity.includes("row"), false);
  assert.equal(identity.includes("provider"), false);
});

test("selected slot exposes creation provenance custody correction and related refs", () => {
  const slot = currentMemoryGeneration().slots.find((item) => item.keyDigest === "c".repeat(64));
  assert.ok(slot);
  assert.equal(slot.createdGeneration, 44_238);
  assert.equal(slot.sourceEligibility, "ELIGIBLE");
  assert.equal(slot.correctionState, "QUALIFIED");
  assert.equal(slot.correctionRef, "requalification:fixture:numeric-source-r9");
  assert.equal(slot.optimizerParticipated, true);
  assert.equal(slot.optimizerUpdateCount, 7);
  assert.equal(slot.sourceRefs.length > 0, true);
  assert.equal(slot.evidenceRefs.length > 0, true);
  assert.equal(slot.capabilities.includes("C.SUCCESSOR"), true);
  assert.equal(slot.episodes.includes("episode-record:fixture:retained-44239"), true);
});

test("rejected candidate cannot appear as committed memory allocation", () => {
  const invariant = rejectedCandidateInvariant(REJECTED_MEMORY_CANDIDATE, currentMemoryGeneration());
  assert.deepEqual(invariant, {
    parentAllocationPreserved: true,
    noCommittedGeneration: true,
    proposedSlotAbsent: true,
    proposedIdentity: REJECTED_MEMORY_CANDIDATE.proposedSlot.keyDigest,
  });
});

test("generation compare identifies created held requalified and metric deltas without pretending append-only rows vanished", () => {
  const delta = memoryCompare(priorMemoryGeneration(), currentMemoryGeneration());
  assert.equal(delta.created.length, 1);
  assert.equal(delta.removed.length, 0);
  assert.equal(delta.held.length, 1);
  assert.equal(delta.requalified.length, 1);
  assert.equal(delta.allocationDelta, 1);
  assert.equal(delta.hitDelta, 5);
  assert.equal(delta.gateUseDelta, 4);
  assert.equal(delta.capacityDelta, 0);
});

test("comparison detects physical removal if supplied but default retained manifest remains append-only", () => {
  const before = priorMemoryGeneration();
  const current = currentMemoryGeneration();
  const syntheticAfter = { ...current, slots: current.slots.slice(1), allocatedSlots: current.allocatedSlots - 1 };
  const delta = memoryCompare(before, syntheticAfter);
  assert.equal(delta.removed.length, 1);
  assert.equal(memoryCompare(before, current).removed.length, 0);
});

test("correction and requalification state is independent of retrieval hit rate", () => {
  const held = currentMemoryGeneration().slots.find((slot) => slot.allocationState === "HELD");
  assert.ok(held);
  assert.equal(held.hitCount > 0, true);
  assert.equal(slotHitRate(held) > 0.5, true);
  assert.equal(held.correctionState, "REQUALIFICATION_REQUIRED");
  assert.equal(held.sourceEligibility, "HELD");
});

test("high hit rate never becomes a learned-success claim without independent capability evidence", () => {
  const slot = currentMemoryGeneration().slots[0];
  assert.equal(slotHitRate(slot), 0.95);
  const interpretation = capabilityInterpretation(slot);
  assert.equal(interpretation.learnedSuccess, false);
  assert.equal(interpretation.capabilityEvidence, "INDEPENDENT_EVIDENCE_UNAVAILABLE");
  assert.match(interpretation.label, /no independent capability claim/i);
});

test("memory deep link uses stable BAMF memory identity and owning view", () => {
  const identity = stableMemoryIdentity(currentMemoryGeneration().slots[0]);
  assert.deepEqual(parseDeepLink(memoryDeepLink(identity)), {
    view: "memory",
    selected: { kind: "memory", id: identity },
  });
  assert.equal(INSPECTOR_OWNERS.memory, "memory");
});

test("GUI10 source avoids memory-policy mutation and unsupported success language", () => {
  const source = [
    "memory-fixture.mjs", "memory-model.mjs", "memory-view.mjs",
  ].map((name) => fs.readFileSync(
    path.join(rendererRoot, "memory", name), "utf8",
  )).join("\n").toLowerCase();
  for (const forbidden of [
    "allocate memory now", "edit memory", "promote slot", "learned success", "semantic authority from memory",
    "providerrowid", "database row id",
  ]) assert.equal(source.includes(forbidden), false, forbidden);
  assert.equal(source.includes("retrieval telemetry only"), true);
  assert.equal(source.includes("not semantic authority"), true);
});

test("CSS gives held rejected and requalified states non-color structural cues", () => {
  const css = fs.readFileSync(path.join(rendererRoot, "memory/memory.css"), "utf8");
  assert.match(css, /data-memory-state="held"/);
  assert.match(css, /border-style:\s*dashed/);
  assert.match(css, /data-memory-state="rejected"/);
  assert.match(css, /data-delta-kind="requalified"/);
});

test("fixture generation sequence is ordered and immutable enough for compare", () => {
  assert.deepEqual(MEMORY_GENERATIONS.map((item) => item.generation), [44_238, 44_239]);
  assert.equal(MEMORY_GENERATIONS.every((item) => Object.isFrozen(item)), true);
});
