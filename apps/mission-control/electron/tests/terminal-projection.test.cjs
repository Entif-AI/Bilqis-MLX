"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");

const REPO_ROOT = path.resolve(__dirname, "../../../..");

test("BAMF terminal preserves completed-step loss during the next live step", () => {
  const python = process.env.BILQIS_PYTHON || "python3";
  const result = spawnSync(
    python,
    [
      "-B", "-m", "unittest",
      "bilqis_mlx.presentation.tests.test_bamf_terminal_projection." +
        "BamfTerminalProjectionTests." +
        "test_active_followup_step_keeps_latest_completed_loss_visible",
      "-q",
    ],
    {
      cwd: REPO_ROOT,
      shell: false,
      encoding: "utf8",
      timeout: 30_000,
    },
  );
  assert.equal(
    result.status,
    0,
    ["Python terminal regression failed.", result.stdout, result.stderr].join("\n"),
  );
});
