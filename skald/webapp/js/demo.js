// The demo: this page with sample data and no helper behind it (tools/demo.py).
// app.json says so ("demo": {text, install, links, api}); without that key
// nothing here changes anything. In the demo:
//   * nothing is posted and no helper address is asked: a save, a refresh or a
//     settings page says politely that it needs a running install
//   * compare and page story read the answers the demo build wrote beside the
//     page (api: {compare: {"A|B": file}, page: {path: file}}); anything else
//     falls back to what the page works out from its own days
//   * a banner says it is sample data, with links to install it

import { h, ICON } from "./ui.js";

export const DEMO = { on: false, text: "", install: "", links: [], api: { compare: {}, page: {} } };
export const DEMO_SAYS = "In the demo, this needs a running Skald.";

export function setDemo(d) {
  if (!d || typeof d !== "object") return;
  DEMO.on = true;
  DEMO.text = String(d.text || "Demo with sample data");
  DEMO.install = String(d.install || "");
  DEMO.links = (Array.isArray(d.links) ? d.links : []).filter((l) => l && /^https:\/\//.test(String(l.url || "")));
  DEMO.api = { compare: d.api?.compare || {}, page: d.api?.page || {} };
}

// A helper address the page would ask ("api/compare?a=..&b=..", "api/page?path=..")
// -> the file the demo build wrote for it, or null: then nothing is fetched.
export function demoFile(url) {
  const [path, q = ""] = String(url).split("?");
  const p = new URLSearchParams(q);
  if (path === "api/compare") {
    if ([...p.keys()].some((k) => k !== "a" && k !== "b")) return null;
    return DEMO.api.compare[`${p.get("a")}|${p.get("b")}`] || null;
  }
  if (path === "api/page") return DEMO.api.page[p.get("path") || ""] || null;
  return null;
}

const link = (l) => h("a", { href: l.url, target: "_blank", rel: "noopener" }, l.text);

// The line at the top of every page: sample data, and where to get the real thing.
export function demoBanner() {
  if (!DEMO.on) return null;
  const links = DEMO.links.map(link);
  return h("div", { class: "demo-banner", role: "note" },
    h("span", { class: "demo-tag" }, "Demo"),
    h("span", { class: "demo-words" }, h("b", null, DEMO.text), DEMO.install ? ` — ${DEMO.install}.` : "."),
    links.length ? h("span", { class: "demo-links" }, links.flatMap((a, i) => (i ? [" · ", a] : [a]))) : null);
}

// A page that only works with a running install (settings, team, integrations).
export function demoState(name) {
  const quick = DEMO.links[0];
  return [h("div", { class: "head" }, h("h1", null, name)),
    h("div", { class: "state demo-state", role: "status", html: ICON.info }, h("div", null,
      h("strong", null, `${DEMO_SAYS} `),
      "Settings, team, integrations and anything that saves are handled by the helper on your own server. The figures in this demo are a fixed sample.",
      quick ? [" ", link({ ...quick, text: `${quick.text}: install it for your site` }), "."] : null))];
}
