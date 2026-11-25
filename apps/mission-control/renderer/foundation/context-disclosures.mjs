const SELECTOR = ".context-disclosure";

export function closeContextDisclosures(document) {
  for (const disclosure of document.querySelectorAll(`${SELECTOR}[open]`)) {
    disclosure.open = false;
  }
}

export function bindContextDisclosures(document) {
  const disclosures = [...document.querySelectorAll(SELECTOR)];
  let tabNavigation = false;
  const dismissOutside = (target) => {
    for (const disclosure of disclosures) {
      if (disclosure.open && !disclosure.contains(target)) disclosure.open = false;
    }
  };
  for (const disclosure of disclosures) {
    disclosure.addEventListener("toggle", () => {
      if (disclosure.open) dismissOutside(disclosure);
    });
  }
  // Dismiss on click, not pointerdown: an in-flow disclosure changes the
  // layout when closed. The pointer must finish activating its intended target.
  document.addEventListener("click", (event) => dismissOutside(event.target), true);
  document.addEventListener("pointerdown", () => { tabNavigation = false; }, true);
  document.addEventListener("focusin", (event) => {
    if (tabNavigation) dismissOutside(event.target);
    tabNavigation = false;
  }, true);
  document.addEventListener("keydown", (event) => {
    tabNavigation = event.key === "Tab";
    if (event.key !== "Escape") return;
    const disclosure = disclosures.find((item) => item.open);
    if (!disclosure) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    disclosure.open = false;
    disclosure.querySelector("summary")?.focus({ preventScroll: true });
  }, true);
}
