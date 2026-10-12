// The site switcher, by bounding boxes (2.6.1), at 1280, 1440, 1680 and 390 px,
// light and dark, from the sidebar's site button, the icon rail's and the phone
// bar's:
//   * every row (logo, name, "N today" or the check) stays inside the menu
//   * the menu stays inside the window and is not cut off by the sidebar: the
//     right end of each row is the topmost thing at its point
// Needs an install with two sites or more (a site's "N today" is what ran past
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
const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };

const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
let checked = 0, sites = 0;
for (const scheme of ["light", "dark"]) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme,
    httpCredentials: auth ? { username: user, password: pass } : undefined });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => fail(`${scheme}: ${e.message}`));
  await p.goto(`${base}#overview`, { waitUntil: "networkidle" });
  if (p.url().includes("/traffic-auth/login")) {
    await p.fill("#email", user);
    await p.fill("#password", pass);
    await p.click("#submit");
    await p.waitForURL((u) => !u.pathname.startsWith("/traffic-auth/"));
    await p.goto(`${base}#overview`, { waitUntil: "networkidle" });
  }
  for (const w of WIDTHS) {
    await p.setViewportSize({ width: w, height: 900 });
    const ways = w < 768 ? [["phone bar", ".tb-title .site-chip"]] : [["sidebar", "#site-slot .site-btn"], ["icon rail", "#site-slot .site-btn"]];
    for (const [way, sel] of ways) {
      const where = `${way} at ${w} ${scheme}`;
      await p.goto(`${base}#overview`, { waitUntil: "networkidle" });
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
        const bad = [];
        for (const row of rows) {
          const name = row.querySelector("b")?.textContent.trim() || "?";
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
        return { bad, rows: rows.length };
      }, sel);
      checked++;
      if (got.none) { fail(`${where}: the menu did not open`); continue; }
      sites = Math.max(sites, got.rows);
      for (const x of got.bad) fail(`${where}: ${x}`);
      await p.keyboard.press("Escape");
    }
  }
  await ctx.close();
}
await b.close();
if (sites < 2) fail(`only ${sites} site in the switcher: this check needs two or more`);
console.log(fails.length ? `${fails.length} problems in ${checked} checks` : `OK: ${checked} checks, ${sites} sites`);
process.exit(fails.length ? 1 : 0);
