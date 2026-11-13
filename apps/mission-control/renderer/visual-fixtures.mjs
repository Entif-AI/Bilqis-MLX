export const VISUAL_FIXTURES = Object.freeze({
  live: { mode: "LIVE", freshness: "FRESH", state: "healthy", label: "Live healthy" },
  historical: { mode: "HISTORICAL", freshness: "FRESH", state: "historical", label: "Historical / as-of" },
  stale: { mode: "LIVE", freshness: "STALE", state: "stale", label: "Stale connection" },
  denied: { mode: "LIVE", freshness: "FRESH", state: "denied", label: "Denied operation" },
  invalidEvidence: { mode: "LIVE", freshness: "FRESH", state: "invalid", label: "Invalid evidence" },
});

export const VISUAL_REGRESSION_CASES = Object.freeze(
  ["dark", "light"].flatMap((theme) =>
    Object.keys(VISUAL_FIXTURES).map((fixture) => Object.freeze({ theme, fixture })),
  ),
);

export function visualFixtureNames() {
  return Object.keys(VISUAL_FIXTURES);
}
