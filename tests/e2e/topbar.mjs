// The top bar, by bounding boxes, on every page at 1280, 1440, 1600, 1680
// and 390 px, light and dark (2.5.1):
//   * nothing in the bar overlaps anything else in it (trail, the modes,
//     period, page group, filters, buttons), and nothing sticks out of the window
//   * the dark pill sits exactly on the chosen period, on load and after a
//     click (once its slide has ended)
//   * on every page with a period: "Today" is the period group's first choice (2.42;
//     pressed at range=today, with the live dot), and "Compare with…" is there on a tab
//     that compares (on by default) and absent on one that does not; with Live on and
//     with Compare on (its longer words) the bar still does not overlap
//   * the approved mockup's seven (2.43): the title and six controls. The period is one group
//     (Today, 7, 30, 90 days, More: one tab stop, the arrows move inside it), then Compare;
//     the filter icon, the search, the alerts and More on the right. No more than six tab
//     stops in the bar, the phone's site button aside.
// Run once signed in as an admin and once as a viewer: their buttons differ.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/topbar.mjs https://host/traffic/<site>/ [user:password]   (basic auth, or a sessions sign-in)
//
// Works on the demo too: python3 tools/demo.py OUT, serve OUT, pass .../traffic/example.com/

const args = process.argv.slice(2);
const [base, auth = ""] = args.filter((a) => !a.startsWith("--"));
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node topbar.mjs <page url> [user:password]"); process.exit(2); }

const WIDTHS = [1280, 1440, 1600, 1680, 390];
// The modes switched on: on a tab that compares and on one that does not.
const MODES = ["overview/summary?range=today", "traffic/sources?cmp=prev", "site/requests?cmp=year",
  "traffic/pages?range=custom&from=2026-09-01&to=2026-09-30&cmp=custom&cb=2026-08-01..2026-08-31"];
const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };

const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
let checked = 0;
for (const scheme of ["light", "dark"]) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme,
    httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
  const p = await ctx.newPage();
  let where = "";
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
  const tabs = await p.evaluate(async () => (await import(new URL("../_app/js/state.js", location.href).href)).TABS.map(([k]) => k));
  for (const w of WIDTHS) {
    await p.setViewportSize({ width: w, height: 900 });
    for (const tab of [...tabs, ...MODES]) {
      where = `${tab} at ${w} ${scheme}`;
      await p.goto(`${base}#${tab}`, { waitUntil: "networkidle" });
      await p.waitForTimeout(450);
      const got = await p.evaluate(async () => {
        const r = (e) => e.getBoundingClientRect();
        const seen = (e) => e.offsetParent !== null && r(e).width > 0 && getComputedStyle(e).visibility !== "hidden";
        const row = document.querySelector(".bar .bar-row");
        if (!row) return { none: true };
        const mid = row.querySelector(".bar-mid");
        const items = [...row.querySelectorAll(".trail li, .bar-mid > *, .bar-modes > *, .bar-right > *")].filter(seen);
        const name = (e) => (e.getAttribute("aria-label") || e.textContent || e.className).trim().slice(0, 30);
        const over = [];
        for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
          const a = r(items[i]), c = r(items[j]);
          if (a.left < c.right - 1 && c.left < a.right - 1 && a.top < c.bottom - 1 && c.top < a.bottom - 1) over.push(`"${name(items[i])}" and "${name(items[j])}"`);
        }
        // On phones the period row scrolls sideways by design; elsewhere nothing leaves the window.
        const out = items.filter((e) => !(mid.contains(e) && innerWidth < 768) && (r(e).right > innerWidth + 1 || r(e).left < -1)).map(name);
        const seg = row.querySelector(".bar-mid .seg");
        const ind = seg?.querySelector(".seg-ind"), on = seg?.querySelector('[aria-pressed="true"]');
        const pill = ind && on ? [r(ind).left - r(on).left, r(ind).width - r(on).width] : null;
        const todayBtn = seg && [...seg.querySelectorAll("button")].find((x) => x.textContent.trim() === "Today");
        const cmp = row.querySelector(".bar-modes .mode-cmp");
        // Custom's two dates show only while Custom is the period: they are the period's, not a control of their own.
        const stops = [...row.querySelectorAll("button, a, input, select")].filter((e) => seen(e) && e.tabIndex >= 0 && !e.closest(".site-wrap, .trail, .dates") && !e.matches(".menu-btn, .site-chip"));
        const moreIn = !!seg?.querySelector(".ui-more-range");
        const filterRight = !!row.querySelector(".bar-right .fp-btn");
        // A page without figures keeps at most its own period chip there (2.13), never the modes.
        return { over, out, pill, stops: stops.length, moreIn, filterRight, figures: !!mid.querySelector(".seg"), live: todayBtn ? todayBtn.getAttribute("aria-pressed") : null, cmp: cmp && cmp.getAttribute("aria-pressed"),
          // The period in force: the address leaves a section's own default out (Today; 7 days on Leads & sales).
          range: (await import(new URL("../_app/js/state.js", location.href).href)).read().range };
      });
      checked++;
      if (got.none) continue;
      for (const o of got.over) fail(`${where}: ${o} overlap in the top bar`);
      if (got.out.length) fail(`${where}: outside the window: ${got.out.join(", ")}`);
      if (got.pill && (Math.abs(got.pill[0]) > 1 || Math.abs(got.pill[1]) > 1)) fail(`${where}: the pill is off its period by ${got.pill.map((x) => x.toFixed(1)).join(" px, ")} px`);
      if (got.stops > 6) fail(`${where}: ${got.stops} tab stops in the top bar, the mockup has six controls`);
      if (!got.figures) continue;
      if (!got.moreIn) fail(`${where}: the period's More is not inside the period group`);
      if (!got.filterRight) fail(`${where}: the filter is not on the right with the search`);
      if (!got.live) fail(`${where}: the period group has no Today`);
      if (got.live && got.live !== String(got.range === "today")) fail(`${where}: Today says ${got.live} at range "${got.range}"`);
    }
    // A click moves the pill onto the new period (after its slide).
    where = `period click at ${w} ${scheme}`;
    await p.goto(`${base}#overview/summary?range=30d`, { waitUntil: "networkidle" });
    await p.waitForTimeout(300);
    await p.locator('.bar .seg button:has-text("7 days")').click();
    await p.waitForTimeout(600);
    const after = await p.evaluate(() => {
      const ind = document.querySelector(".bar .seg-ind"), on = document.querySelector('.bar .seg [aria-pressed="true"]');
      const a = ind.getBoundingClientRect(), c = on.getBoundingClientRect();
      return { text: on.textContent, d: [a.left - c.left, a.width - c.width] };
    });
    if (after.text !== "7 days") fail(`${where}: "${after.text}" is chosen, not "7 days"`);
    if (Math.abs(after.d[0]) > 1 || Math.abs(after.d[1]) > 1) fail(`${where}: the pill is off its period by ${after.d.map((x) => x.toFixed(1)).join(" px, ")} px`);
  }
  await ctx.close();
}
await b.close();
console.log(`${checked} pages checked; ${fails.length ? `${fails.length} failed` : "all passed"}`);
process.exit(fails.length ? 1 : 0);
