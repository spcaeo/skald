// The site switcher, by bounding boxes (2.6.1), at 1280, 1440, 1680 and 390 px,
// light and dark, from the sidebar's site button, the icon rail's and the phone
// bar's:
//   * every row (logo, name, "N today" or the check) stays inside the menu
//   * the menu stays inside the window and is not cut off by the sidebar: the
//     right end of each row is the topmost thing at its point
//   * SKALD-35: in a short window (600 px) too; a long list scrolls inside the
//     menu (each row is checked once scrolled into the list's view) and All
//     sites stays on screen
//   * SKALD-35: with "Find a site" (7 sites or more), typing a site's name keeps
//     that row, a name no site has shows "No site matches" and All sites, and
//     Escape empties the box before it closes the menu
// Needs an install with two sites or more, seven or more for the search box (a site's "N today" is what ran past
// the menu before 2.6.1). Signs in on the sessions sign-in page when sent there,
// or uses basic auth.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/switcher.mjs https://host/traffic/<site>/ [email:password]

const args = process.argv.slice(2);
const [base, auth = ""] = args.filter((a) => !a.startsWith("--"));
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node switcher.mjs <page url> [email:password]"); process.exit(2); }
const [user, ...rest] = auth.split(":");
const pass = rest.join(":");

const WIDTHS = [1280, 1440, 1680, 390];
const HEIGHTS = [900, 600];
const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };

const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
let checked = 0, sites = 0, searched = 0;
for (const scheme of ["light", "dark"]) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme,
    httpCredentials: auth ? { username: user, password: pass } : undefined });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => fail(`${scheme}: ${e.message}`));
  await p.goto(`${base}#overview/summary`, { waitUntil: "networkidle" });
  if (p.url().includes("/traffic-auth/login")) {
    await p.fill("#email", user);
    await p.fill("#password", pass);
    await p.click("#submit");
    await p.waitForURL((u) => !u.pathname.startsWith("/traffic-auth/"));
    await p.goto(`${base}#overview/summary`, { waitUntil: "networkidle" });
  }
  for (const w of WIDTHS) for (const ht of HEIGHTS) {
    await p.setViewportSize({ width: w, height: ht });
    const ways = w < 768 ? [["phone bar", ".tb-title .site-chip"]] : [["sidebar", "#site-slot .site-btn"], ["icon rail", "#site-slot .site-btn"]];
    for (const [way, sel] of ways) {
      const where = `${way} at ${w}x${ht} ${scheme}`;
      await p.goto(`${base}#overview/summary`, { waitUntil: "networkidle" });
      await p.evaluate((icons) => { document.getElementById("app").dataset.rail = icons ? "icons" : ""; }, way === "icon rail");
      await p.waitForTimeout(300);
      const btn = p.locator(sel).first();
      if (!(await btn.isVisible())) { fail(`${where}: no site button`); continue; }
      await btn.click();
      await p.waitForTimeout(350);
      const got = await p.evaluate((sel) => {
        const menu = document.querySelector(sel).closest(".site-wrap").querySelector(".site-menu");
        if (!menu || menu.hidden) return { none: true };
        const m = menu.getBoundingClientRect();
        const rows = [...menu.querySelectorAll(".site-i")];
        const list = menu.querySelector(".site-list");
        const bad = [];
        for (const row of rows) {
          const name = row.querySelector("b")?.textContent.trim() || "?";
          // A long list scrolls: bring the row into the list's view first.
          if (list) {
            const lr = list.getBoundingClientRect(), rr = row.getBoundingClientRect();
            if (rr.top < lr.top || rr.bottom > lr.bottom) list.scrollTop += rr.top - lr.top;
          }
          const r = row.getBoundingClientRect();
          if (r.left < m.left - 1 || r.right > m.right + 1 || row.scrollWidth > row.clientWidth + 1) bad.push(`"${name}" runs past the menu`);
          const end = row.querySelector(".si-end");
          if (end) {
            const e = end.getBoundingClientRect();
            if (e.right > m.right + 1) bad.push(`"${name}": its end runs past the menu`);
            const top = document.elementFromPoint(Math.min(e.right - 2, innerWidth - 1), e.top + e.height / 2);
            if (!top || !row.contains(top)) bad.push(`"${name}": its end is hidden`);
          }
        }
        if (m.right > innerWidth + 1 || m.left < -1 || m.bottom > innerHeight + 1) bad.push("the menu leaves the window");
        const all = menu.querySelector(".site-all"), a = all?.getBoundingClientRect();
        if (!all) bad.push("no All sites");
        else if (!all.contains(document.elementFromPoint(a.left + a.width / 2, a.top + a.height / 2))) bad.push("All sites is hidden");
        const names = rows.map((x) => x.querySelector("b")?.firstChild?.textContent.trim()).filter(Boolean);
        return { bad, rows: rows.length, last: names[names.length - 1], find: !!menu.querySelector(".site-find-in") };
      }, sel);
      checked++;
      if (got.none) { fail(`${where}: the menu did not open`); continue; }
      sites = Math.max(sites, got.rows);
      for (const x of got.bad) fail(`${where}: ${x}`);
      if (got.find) {
        searched++;
        const box = p.locator(sel).first().locator("xpath=ancestor::*[contains(@class,'site-wrap')][1]").locator(".site-find-in");
        const seen = () => p.evaluate((sel) => {
          const menu = document.querySelector(sel).closest(".site-wrap").querySelector(".site-menu");
          const shown = [...menu.querySelectorAll("a.site-i")].filter((x) => !x.closest("[hidden]"));
          return { open: !menu.hidden, value: menu.querySelector(".site-find-in").value,
            names: shown.map((x) => x.querySelector("b")?.firstChild?.textContent.trim()),
            none: !menu.querySelector(".site-none").hidden, all: !menu.querySelector(".site-all").closest("[hidden]") };
        }, sel);
        await box.fill(got.last);
        let s = await seen();
        if (!s.names.includes(got.last)) fail(`${where}: searching "${got.last}" hides its own row`);
        if (s.names.length >= got.rows) fail(`${where}: searching "${got.last}" hides nothing`);
        await box.fill("no-such-site-zz");
        s = await seen();
        if (s.names.length || !s.none || !s.all) fail(`${where}: a name no site has: rows ${s.names.length}, "No site matches" ${s.none}, All sites ${s.all}`);
        await box.press("Escape");
        s = await seen();
        if (!s.open || s.value || s.names.length !== got.rows) fail(`${where}: the first Escape should empty the box and keep the menu open`);
      }
      await p.keyboard.press("Escape");
    }
  }
  await ctx.close();
}
await b.close();
if (sites < 2) fail(`only ${sites} site in the switcher: this check needs two or more`);
console.log(fails.length ? `${fails.length} problems in ${checked} checks` : `OK: ${checked} checks (${searched} with the search box), ${sites} sites`);
process.exit(fails.length ? 1 : 0);
