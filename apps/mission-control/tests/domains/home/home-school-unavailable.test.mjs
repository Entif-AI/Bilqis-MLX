import assert from "node:assert/strict";
import test from "node:test";

import { referenceHomeProjection } from "../../../renderer/home/home-fixture.mjs";
import { renderHomeMarkup } from "../../../renderer/home/home-view.mjs";

test("unavailable capability evidence is not rendered as a truthful zero-row school snapshot", () => {
  const fixture = referenceHomeProjection();
  const model = {
    ...fixture,
    state: Object.freeze({ ...fixture.state, capability: "UNAVAILABLE" }),
    schoolRows: Object.freeze([]),
  };

  const markup = renderHomeMarkup(model);

  const school = markup.match(/<section class="home-analysis home-school"[\s\S]*?<\/section>/)?.[0] ?? "";
  assert.match(school, /<span>Unavailable<\/span>/);
  assert.doesNotMatch(school, />0 rows<\//);
});
