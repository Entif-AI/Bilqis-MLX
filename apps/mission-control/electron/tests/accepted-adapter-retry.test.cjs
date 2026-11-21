"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { AcceptedControlPlaneAdapter } = require("../accepted-control-plane-adapter.cjs");

function transient(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

function adapterFor(broker) {
  return new AcceptedControlPlaneAdapter({
    broker,
    retryDelaysMs: [0, 0, 0],
    sleep: async () => {},
  });
}

test("accepted adapter retries transient read-only CP03 failures but never duplicates commands", async () => {
  let queryAttempts = 0;
  let commandAttempts = 0;
  const broker = {
    async query() {
      queryAttempts += 1;
      if (queryAttempts < 3) throw transient("BAMF_GUI20_CP01_TIMEOUT");
      return { accepted: true, state: "EMPTY", records: [] };
    },
    async submitCommand() {
      commandAttempts += 1;
      throw transient("BAMF_GUI20_CP01_TIMEOUT");
    },
    close() {},
  };
  const adapter = adapterFor(broker);

  await adapter.query(adapter.session, { family: "semantic" });
  assert.equal(queryAttempts, 3);
  await assert.rejects(
    adapter.command(adapter.session, { request: {}, expectedTargetRef: "target:fixture" }),
    /BAMF_GUI20_CP01_TIMEOUT/,
  );
  assert.equal(commandAttempts, 1);
});

test("accepted adapter retries transient CP04 startup until one real subscription owns teardown", async () => {
  let attempts = 0;
  let stops = 0;
  const broker = {
    async subscribe() {
      attempts += 1;
      if (attempts < 3) throw transient("BAMF_GUI20_CP01_PROCESS_UNAVAILABLE");
      return () => { stops += 1; };
    },
    close() {},
  };
  const adapter = adapterFor(broker);

  const stop = await adapter.subscribe(adapter.session, () => {});
  assert.equal(attempts, 3);
  stop();
  assert.equal(stops, 1);
});
