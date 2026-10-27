// Every tab, at every range and page group: one-line headers, none of the
// old intro sentences, no sideways scroll (at 390 too), no console error - and on a short
// window the sidebar's last section, its foot and the page footer reachable.
// The menu (2.7.0): the five sections, Settings, Help and About in its foot;
// a section's tab strip sits outside the page's one-line header. Every old
// address and its redirect: tests/e2e/routes.mjs.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/layout.mjs https://host/traffic/<site>/ [user:password] [--quick]
//
// --quick: the whole site at every range; each other page group at 30 days only.

const args = process.argv.slice(2);
const quick = args.includes("--quick");
const [base, auth = ""] = args.filter((a) => !a.startsWith("--"));
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node layout.mjs <page url> [user:password] [--quick]"); process.exit(2); }

const TABS = ["overview/summary", "overview/insights", "site/requests", "traffic/visitors", "traffic/sources", "traffic/pages", "sales/pipeline", "sales/bookings", "sales/funnels", "sales/events",
  "traffic/places", "traffic/time", "ai/assistants", "ai/rules", "site/health", "site/alerts", "site/quality", "site/speed", "site/notfound", "settings/home", "settings/site/internal", "settings/site/collect", "settings/ai/mcp", "settings/help", "about"];
const SECTIONS = ["overview", "traffic", "leads & sales", "ai & bots", "site"];
const OLD = [/recounted every two minutes/i, /covering 00:00/i, /in five groups that add up exactly/i, /Live and partial/i, /Today from local midnight/i];
const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };

const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 },
  httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
const p = await ctx.newPage();
let where = "";
p.on("console", (m) => { if (m.type() === "error") fail(`${where}: console error ${m.text()}`); });
p.on("pageerror", (e) => fail(`${where}: ${e.message}`));

await p.goto(`${base}#overview/summary`, { waitUntil: "networkidle" });
// A sessions install sends the browser to its sign-in page: sign in there (as switcher.mjs does).
if (p.url().includes("/traffic-auth/login") && auth) {
  await p.fill("#email", auth.split(":")[0]);
  await p.fill("#password", auth.split(":").slice(1).join(":"));
  await p.click("#submit");
  await p.waitForURL((u) => !u.pathname.startsWith("/traffic-auth/"));
  await p.goto(`${base}#overview/summary`, { waitUntil: "networkidle" });
}
// The page groups: in the Filters panel since 2.42 (it was a list in the top bar).
await p.click(".bar .fp-btn");
const views = await p.evaluate(() => [...document.querySelectorAll(".fp-group option")].map((o) => o.value));
await p.keyboard.press("Escape");
const groups = views.length ? views : ["all"];
let pages = 0;
for (const view of groups) {
  const ranges = view === "all" || !quick ? ["today", "7d", "30d", "90d", "custom"] : ["30d"];
  for (const range of ranges) {
    for (const tab of TABS) {
      where = `${tab} ${range} ${view}`;
      const q = new URLSearchParams({ range });
      if (view !== "all") q.set("view", view);
      if (range === "custom") { q.set("from", "2026-09-20"); q.set("to", "2026-10-06"); }
      await p.goto(`${base}#${tab}?${q}`, { waitUntil: "networkidle" });
      await p.waitForTimeout(250);
      const got = await p.evaluate(() => {
        const head = document.querySelector("#panel > .head, #panel .stabs-panel > .head");
        const strip = document.querySelector("#panel .stabs-list");
        const words = [document.body.innerText, ...[...document.querySelectorAll("[aria-label],[title]")].map((e) => `${e.getAttribute("aria-label") || ""} ${e.getAttribute("title") || ""}`)].join("\n");
        return { headH: head ? head.getBoundingClientRect().height : 0, words, over: document.documentElement.scrollWidth - innerWidth,
          strip: strip ? !strip.closest(".head") && (!head || head.getBoundingClientRect().top >= strip.getBoundingClientRect().bottom - 1) : null };
      });
      pages++;
      if (got.headH > 30) fail(`${where}: header block is ${Math.round(got.headH)}px tall, more than one line`);
      for (const re of OLD) if (re.test(got.words)) fail(`${where}: old wording "${re.source}" on the page`);
      if (got.over > 1) fail(`${where}: sideways scroll of ${got.over}px`);
      if (tab.includes("/") && !tab.startsWith("settings/") && got.strip !== true) fail(`${where}: no tab strip above the page's header`);
    }
  }
}

// The menu: the five sections, every label once (no item named like a group), all of it in
// view at 1440x800, and when it must scroll, no item ever under the brand block. Its foot:
// Settings, Help and About, then one row of buttons (theme, what's new, you, fold).
await p.setViewportSize({ width: 1440, height: 800 });
where = "menu at 1440x800";
await p.goto(`${base}#overview/summary?range=today`, { waitUntil: "networkidle" });
const menu = await p.evaluate(() => {
  const items = [...document.querySelectorAll(".nav .tab")].map((b) => b.textContent.trim().toLowerCase());
  const heads = [...document.querySelectorAll(".nav .nav-h")].map((e) => e.textContent.trim().toLowerCase());
  const nav = document.querySelector(".nav");
  const links = [...document.querySelectorAll(".rail-foot > .gear, .rail-foot > .foot-link")].filter((e) => e.offsetParent !== null).map((e) => e.textContent.trim());
  const footRow = [...document.querySelectorAll(".rail-foot > :not(.gear):not(.foot-link)")].filter((e) => e.offsetParent !== null).map((e) => Math.round(e.getBoundingClientRect().top));
  return { items, heads, links, scrolls: nav.scrollHeight > nav.clientHeight + 1, footRows: new Set(footRow).size };
});
const all = [...menu.items, ...menu.heads];
const dup = all.filter((x, i) => all.indexOf(x) !== i);
if (dup.length) fail(`${where}: a label appears twice: ${[...new Set(dup)].join(", ")}`);
if (menu.items.join() !== SECTIONS.join()) fail(`${where}: the menu is ${menu.items.join(", ")}, not the five sections`);
if (menu.links.join() !== "Settings,Help,About Skald") fail(`${where}: the foot's links are ${menu.links.join(", ")}`);
if (menu.scrolls) fail(`${where}: the menu does not fit without scrolling`);
if (menu.footRows !== 1) fail(`${where}: the sidebar foot's buttons are ${menu.footRows} rows, not one`);
for (const [w, hgt] of [[1440, 600], [1280, 560]]) {
  await p.setViewportSize({ width: w, height: hgt });
  where = `menu at ${w}x${hgt}`;
  await p.goto(`${base}#overview/summary?range=today`, { waitUntil: "networkidle" });
  const covered = await p.evaluate(() => {
    const nav = document.querySelector(".nav"), brand = document.querySelector(".brand").getBoundingClientRect();
    const out = [];
    for (const top of [0, nav.scrollHeight]) {
      nav.scrollTop = top;
      for (const b of nav.querySelectorAll(".tab")) {
        // Only the part the menu itself shows; an item cut by the menu's own scroll edge is not covered.
        const r = b.getBoundingClientRect(), n = nav.getBoundingClientRect();
        const top = Math.max(r.top, n.top), bottom = Math.min(r.bottom, n.bottom);
        if (bottom - top < 4) continue;
        const hit = document.elementFromPoint(r.left + r.width / 2, (top + bottom) / 2);
        if (top < brand.bottom - 1 || !b.contains(hit)) out.push(b.textContent.trim());
      }
    }
    return out;
  });
  if (covered.length) fail(`${where}: under the brand block: ${covered.join(", ")}`);
}
// About: the table header never slides under the sub-nav, and a jump to any
// module leaves its heading and first row in view below that header.
for (const [w, hgt] of [[1440, 900], [1024, 800]]) {
  await p.setViewportSize({ width: w, height: hgt });
  where = `about compare at ${w}`;
  await p.goto(`${base}#about?part=compare`, { waitUntil: "networkidle" });
  await p.waitForTimeout(500);
  const bad = await p.evaluate(async () => {
    const out = [], sub = document.querySelector(".about-nav"), head = document.querySelector("table.cmp2 thead th");
    for (const row of document.querySelectorAll("table.cmp2 .mod-r")) {
      row.scrollIntoView({ block: "start" });
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const s = sub.getBoundingClientRect(), hd = head.getBoundingClientRect(), m = row.getBoundingClientRect();
      const first = row.parentElement.querySelector("tr:not(.mod-r):not(.grp-r)")?.getBoundingClientRect();
      if (hd.top < s.bottom - 1) out.push(`header at ${Math.round(hd.top)}, under the sub-nav (ends at ${Math.round(s.bottom)})`);
      if (m.top < hd.bottom - 1) out.push(`"${row.textContent.slice(0, 30)}" lands under the header`);
      if (first && first.bottom > innerHeight) out.push(`"${row.textContent.slice(0, 30)}": its first row is off screen`);
    }
    return out;
  });
  for (const b of bad) fail(`${where}: ${b}`);
}

// Old links open the renamed sections: the bar names the section, the strip the tab
// (every old address: tests/e2e/routes.mjs).
await p.setViewportSize({ width: 1440, height: 800 });
for (const [old, name, tab] of [["visits", "Traffic", "Visitors"], ["audience", "Traffic", "Places & devices"], ["hours", "Traffic", "Time"], ["alerts", "Site", "Alerts"],
  ["quality", "Site", "Data quality"], ["ours", "Internal traffic", null], ["broken", "Site", "Not found"], ["leads", "Leads & sales", "Pipeline"], ["bots", "AI & bots", "Assistants"]]) {
  where = `old link #${old}`;
  await p.goto(`${base}#${old}`, { waitUntil: "networkidle" });
  const now = await p.evaluate(() => [document.querySelector(".trail .crumb.now")?.textContent, document.querySelector('.stabs [aria-selected="true"] .stab-name')?.textContent || null]);
  if (now[0] !== name || now[1] !== tab) fail(`${where}: opened "${now.join(" > ")}", not "${[name, tab].filter(Boolean).join(" > ")}"`);
}

// A phone (390 px): no tab or settings page scrolls sideways (2.13: a grid's .vh spans
// escaped its scroller, and the doctor's fix line on Integrations did not wrap). A settings
// page that needs a signed-in helper shows its own state on the demo; that is checked too.
await p.setViewportSize({ width: 390, height: 800 });
for (const tab of [...TABS, "overview/realtime", "traffic/search", "traffic/retention", "sales/people", "ai/crawl", "ai/crawlers",
  "settings/site/details", "settings/site/mail", "settings/site/leads", "settings/ai/tokens", "settings/org/team", "help"]) {
  where = `${tab} at 390`;
  await p.goto(`${base}#${tab}?range=30d`, { waitUntil: "networkidle" });
  await p.waitForTimeout(250);
  const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (over > 1) fail(`${where}: sideways scroll of ${over}px`);
}

// A short window: the sidebar's last section and its foot, and the page footer, can be reached.
for (const [w, hgt] of [[1440, 600], [1440, 700], [1280, 560]]) {
  await p.setViewportSize({ width: w, height: hgt });
  where = `short window ${w}x${hgt}`;
  await p.goto(`${base}#overview/summary?range=today`, { waitUntil: "networkidle" });
  const r = await p.evaluate(() => {
    const nav = document.querySelector(".nav");
    nav.scrollTop = nav.scrollHeight;
    const last = [...document.querySelectorAll(".nav .tab")].pop().getBoundingClientRect();
    const foot = [...document.querySelectorAll(".rail-foot > *")].filter((e) => e.offsetParent !== null);
    const fb = foot.map((e) => e.getBoundingClientRect());
    scrollTo(0, document.documentElement.scrollHeight);
    const pf = document.getElementById("foot").getBoundingClientRect();
    return { last: [last.top, last.bottom], foot: fb.map((x) => [x.top, x.bottom]), page: [pf.top, pf.bottom], h: innerHeight };
  });
  if (r.last[0] < 0 || r.last[1] > r.h + 1) fail(`${where}: the last section is outside the window (${r.last})`);
  if (!r.foot.length || r.foot.some(([t, bt]) => t < 0 || bt > r.h - 8)) fail(`${where}: the sidebar's foot is cut off (${JSON.stringify(r.foot)} in ${r.h})`);
  if (r.page[1] > r.h + 1) fail(`${where}: the page footer is cut off`);
}
await b.close();
console.log(`${pages} pages checked; ${fails.length ? `${fails.length} failed` : "all passed"}`);
process.exit(fails.length ? 1 : 0);
