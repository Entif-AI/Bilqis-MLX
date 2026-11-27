"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");

const REPO_ROOT = path.resolve(__dirname, "../../../..");

test("native query source preserves cache and request identity", () => {
  const python = process.env.BILQIS_PYTHON || "python3";
  const result = spawnSync(
    python,
    [
      "-B", "-m", "unittest",
"bilqis_mlx.control_plane.tests.cp07.native.test_native_query_cache",
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
    ["Python native-query regression failed.", result.stdout, result.stderr].join("\n"),
  );
});
