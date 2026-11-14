"use strict";

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const { RENDERER_HOST, RENDERER_SCHEME } = require("./renderer-location.cjs");

const RENDERER_ASSETS = Object.freeze(new Map([
  ["/component-catalog.mjs", "component-catalog.mjs"],
  ["/components.css", "components.css"],
  ["/deep-link.mjs", "deep-link.mjs"],
  ["/episode-fixture.mjs", "episode-fixture.mjs"],
  ["/episode-model.mjs", "episode-model.mjs"],
  ["/episode-view.mjs", "episode-view.mjs"],
  ["/episodes.css", "episodes.css"],
  ["/index.html", "index.html"],
  ["/neural-fixture.mjs", "neural-fixture.mjs"],
  ["/neural-model.mjs", "neural-model.mjs"],
  ["/neural-view.mjs", "neural-view.mjs"],
  ["/neural.css", "neural.css"],
  ["/renderer.mjs", "renderer.mjs"],
  ["/semantic-atlas.css", "semantic-atlas.css"],
  ["/semantic-atlas.mjs", "semantic-atlas.mjs"],
  ["/school-fixture.mjs", "school-fixture.mjs"],
  ["/school-model.mjs", "school-model.mjs"],
  ["/school-view.mjs", "school-view.mjs"],
  ["/school.css", "school.css"],
  ["/settings.mjs", "settings.mjs"],
  ["/shell-state.mjs", "shell-state.mjs"],
  ["/shell.css", "shell.css"],
  ["/visual-fixtures.mjs", "visual-fixtures.mjs"],
  ["/visual-language.mjs", "visual-language.mjs"],
  ["/visual-tokens.css", "visual-tokens.css"],
]));

function assetPathForRendererRequest(requestUrl, assetRoot) {
  if (typeof assetRoot !== "string" || assetRoot.length === 0 || !path.isAbsolute(assetRoot)) {
    throw new TypeError("BAMF_GUI20_RENDERER_ASSET_ROOT_REQUIRED");
  }
  let request;
  try {
    request = new URL(requestUrl);
  } catch (_error) {
    return null;
  }
  if (request.protocol !== `${RENDERER_SCHEME}:` || request.hostname !== RENDERER_HOST ||
      request.username || request.password || request.port || request.search) {
    return null;
  }
  const relative = RENDERER_ASSETS.get(request.pathname);
  return relative ? path.join(assetRoot, relative) : null;
}

function registerMissionControlProtocol({ protocol, net, assetRoot }) {
  if (!protocol || typeof protocol.handle !== "function") {
    throw new TypeError("BAMF_GUI20_PROTOCOL_REQUIRED");
  }
  if (!net || typeof net.fetch !== "function") {
    throw new TypeError("BAMF_GUI20_NET_REQUIRED");
  }
  protocol.handle(RENDERER_SCHEME, (request) => {
    const asset = assetPathForRendererRequest(request.url, assetRoot);
    if (asset === null) {
      return new Response("Not found", {
        status: 404,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
    return net.fetch(pathToFileURL(asset).href);
  });
}

module.exports = {
  RENDERER_ASSETS,
  assetPathForRendererRequest,
  registerMissionControlProtocol,
};
