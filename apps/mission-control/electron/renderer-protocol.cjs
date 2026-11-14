"use strict";

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const { RENDERER_HOST, RENDERER_SCHEME } = require("./renderer-location.cjs");

const RENDERER_ASSETS = Object.freeze(new Map([
  ["/component-catalog.mjs", "component-catalog.mjs"],
  ["/components.css", "components.css"],
  ["/deep-link.mjs", "deep-link.mjs"],
  ["/domains/episode-fixture.mjs", "domains/episode-fixture.mjs"],
  ["/domains/episode-model.mjs", "domains/episode-model.mjs"],
  ["/domains/episode-view.mjs", "domains/episode-view.mjs"],
  ["/domains/episodes.css", "domains/episodes.css"],
  ["/index.html", "index.html"],
  ["/domains/neural-fixture.mjs", "domains/neural-fixture.mjs"],
  ["/domains/neural-model.mjs", "domains/neural-model.mjs"],
  ["/domains/neural-view.mjs", "domains/neural-view.mjs"],
  ["/domains/neural.css", "domains/neural.css"],
  ["/renderer.mjs", "renderer.mjs"],
  ["/domains/semantic-atlas.css", "domains/semantic-atlas.css"],
  ["/domains/semantic-atlas.mjs", "domains/semantic-atlas.mjs"],
  ["/domains/school-fixture.mjs", "domains/school-fixture.mjs"],
  ["/domains/school-model.mjs", "domains/school-model.mjs"],
  ["/domains/school-view.mjs", "domains/school-view.mjs"],
  ["/domains/school.css", "domains/school.css"],
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
