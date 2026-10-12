// The vendored Folder Tabs and Data Grid, mounted through Skald's adapters the way a
// section does: the hash is the route, every route change redraws the panel.
import { folderTabs } from "../../../skald/webapp/js/foldertabs.js";
import { grid, HASH } from "../../../skald/webapp/js/grid.js";
import { liveCount, sweep } from "../../../skald/webapp/js/mounts.js";
import { REGISTRY } from "../../../skald/webapp/js/table.js";
import { h } from "../../../skald/webapp/js/ui.js";

const TABS = [["demo/one", "Pages"], ["demo/two", "Two"], ["demo/locked", "Locked", true], ["demo/three", "Three"], ["demo/four", "Four"]];
const KINDS = ["blog", "docs", "shop"];
// 60 rows: every fifth path has "beta" in it, every seventh title was not recorded.
const ROWS = Array.from({ length: 60 }, (_, i) => ({
  id: i, path: i % 5 === 0 ? `/beta-${i}/` : `/page-${i}/`, kind: KINDS[i % 3],
  views: (i * 37) % 101, title: i % 7 === 0 ? null : `Title ${i}`,
}));

const route = () => {
  const r = location.hash.replace(/^#/, "").split("?")[0];
  return TABS.some(([k]) => k === r) ? r : "demo/one";
};
// A tab's link carries the page's own keys (the period), not another tab's grid keys.
const hrefFor = (key) => {
  const keep = new URLSearchParams();
  const range = HASH.read().get("range");
  if (range) keep.set("range", range);
  return `#${key}${keep.toString() ? `?${keep}` : ""}`;
};

let renders = 0, opened = null;
function render() {
  renders++;
  REGISTRY.length = 0;
  const key = route();
  const content = [h("h1", null, TABS.find(([k]) => k === key)[1])];
  if (key === "demo/one") {
    content.push(grid({
      ns: "pg", caption: "Pages read", file: "pages.csv", rows: ROWS, rowId: (r) => r.id,
      columns: [{ key: "path", label: "Page" }, { key: "title", label: "Title" }, { key: "kind", label: "Kind" }, { key: "views", label: "Views", num: true }],
      filters: [{ key: "kind", label: "Kind" }],
      onFiltered: (all) => { document.getElementById("totals").textContent = `Filtered: ${all.length}; views ${all.reduce((s, r) => s + r.views, 0)}`; },
      onRow: (row) => { opened = row.path; },
    }));
  } else content.push(h("p", null, `The ${key} tab.`));
  const tabs = folderTabs({
    name: "demo", label: "Demo sections", active: key, content,
    tabs: TABS.map(([k, label, off]) => ({ key: k, label, href: hrefFor(k), disabled: !!off, title: off ? "Not on this plan" : null })),
  });
  document.getElementById("panel").replaceChildren(tabs);
}
addEventListener("hashchange", render);
render();

window.demo = {
  liveCount, sweep, redraw: render,
  renders: () => renders,
  opened: () => opened,
  registry: () => REGISTRY.map((t) => t.rows().length),
};
