export const THEMES = Object.freeze(["dark", "light"]);
export const DENSITIES = Object.freeze(["comfortable", "compact", "terminal"]);

function allowed(value, choices, fallback) {
  return choices.includes(value) ? value : fallback;
}

export function loadDisplaySettings(storage) {
  return {
    theme: allowed(storage?.getItem("bilqis.mc.theme"), THEMES, "dark"),
    density: allowed(storage?.getItem("bilqis.mc.density"), DENSITIES, "comfortable"),
  };
}

export function saveDisplaySettings(storage, settings) {
  storage?.setItem("bilqis.mc.theme", allowed(settings.theme, THEMES, "dark"));
  storage?.setItem("bilqis.mc.density", allowed(settings.density, DENSITIES, "comfortable"));
}

export function cycleSetting(value, choices) {
  const index = choices.indexOf(value);
  return choices[(index + 1 + choices.length) % choices.length];
}

export function applyDisplaySettings(root, settings) {
  root.dataset.theme = allowed(settings.theme, THEMES, "dark");
  root.dataset.density = allowed(settings.density, DENSITIES, "comfortable");
}
