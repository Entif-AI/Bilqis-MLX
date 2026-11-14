"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { RENDERER_ENTRY_URL } = require("../renderer-location.cjs");
const {
  RENDERER_ASSETS,
  assetPathForRendererRequest,
  registerMissionControlProtocol,
} = require("../renderer-protocol.cjs");

test("renderer protocol resolves only the checked-in Mission Control asset allowlist", () => {
  const root = "/Applications/Bilqis/MissionControl/renderer";
  assert.equal(
    assetPathForRendererRequest(RENDERER_ENTRY_URL, root),
    `${root}/index.html`,
  );
  assert.equal(
    assetPathForRendererRequest("bamf-mc://app/renderer.mjs", root),
    `${root}/renderer.mjs`,
  );
  assert.deepEqual([...RENDERER_ASSETS.keys()].sort(), [
    "/component-catalog.mjs",
    "/components.css",
    "/deep-link.mjs",
    "/domains/controller.mjs",
    "/domains/episodes/episode-fixture.mjs",
    "/domains/episodes/episode-model.mjs",
    "/domains/episodes/episode-view.mjs",
    "/domains/episodes/episodes.css",
    "/domains/memory/memory-fixture.mjs",
    "/domains/memory/memory-model.mjs",
    "/domains/memory/memory-view.mjs",
    "/domains/memory/memory.css",
    "/domains/neural/neural-fixture.mjs",
    "/domains/neural/neural-model.mjs",
    "/domains/neural/neural-view.mjs",
    "/domains/neural/neural.css",
    "/domains/school/school-fixture.mjs",
    "/domains/school/school-model.mjs",
    "/domains/school/school-view.mjs",
    "/domains/school/school.css",
    "/domains/semantic/semantic-atlas.css",
    "/domains/semantic/semantic-atlas.mjs",
    "/index.html",
    "/renderer.mjs",
    "/settings.mjs",
    "/shell-state.mjs",
    "/shell.css",
    "/visual-fixtures.mjs",
    "/visual-language.mjs",
    "/visual-tokens.css",
  ]);
});

test("renderer protocol refuses traversal, query aliases and untrusted origins", () => {
  const root = "/Applications/Bilqis/MissionControl/renderer";
  for (const requestUrl of [
    "bamf-mc://app/../main.cjs",
    "bamf-mc://app/%2e%2e/main.cjs",
    "bamf-mc://app/index.html?file=../../main.cjs",
    "bamf-mc://other/index.html",
    "file:///etc/passwd",
    "https://evil.example/index.html",
  ]) {
    assert.equal(assetPathForRendererRequest(requestUrl, root), null, requestUrl);
  }
  assert.throws(
    () => assetPathForRendererRequest(RENDERER_ENTRY_URL, "relative/renderer"),
    /BAMF_GUI20_RENDERER_ASSET_ROOT_REQUIRED/,
  );
});

test("protocol handler never asks net.fetch for a non-allowlisted local file", async () => {
  let handler;
  const fetched = [];
  registerMissionControlProtocol({
    protocol: {
      handle(scheme, next) {
        assert.equal(scheme, "bamf-mc");
        handler = next;
      },
    },
    net: {
      fetch(url) {
        fetched.push(url);
        return Promise.resolve(new Response("ok"));
      },
    },
    assetRoot: "/Applications/Bilqis/MissionControl/renderer",
  });

  const allowed = await handler({ url: RENDERER_ENTRY_URL });
  assert.equal(await allowed.text(), "ok");
  assert.match(fetched[0], /^file:\/\/\/Applications\/Bilqis\/MissionControl\/renderer\/index\.html$/);

  const denied = await handler({ url: "bamf-mc://app/../main.cjs" });
  assert.equal(denied.status, 404);
  assert.equal(fetched.length, 1);
});
