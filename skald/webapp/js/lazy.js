// A panel that waits for its big files (data.js LAZY) on its own (2.41): the page is drawn
// at once, the panel shows its title and "Loading" in its place, and is drawn when its files
// come. A page drawn again meanwhile (another tab, another period) leaves the old panel be.

import { h } from "./ui.js";
import { has, need } from "./data.js";

export function later(m, names, build, title) {
  if (has(m, names)) return build();
  const box = h("section", { class: "s lazy-wait", "aria-busy": "true", "data-lazy": names.join(" ") },
    h("h2", null, title), h("p", { class: "muted", role: "status" }, "Loading…"));
  need(m, names).then(() => {
    if (!box.isConnected) return;
    const drawn = [build()].flat(Infinity).filter(Boolean);
    if (drawn.length) box.replaceWith(...drawn);
    else box.remove();
  }).catch(() => {
    if (!box.isConnected) return;
    box.removeAttribute("aria-busy");
    box.lastChild.textContent = "Could not be loaded: reload the page to try again.";
  });
  return box;
}
