// Finding and moving (2.13), in a real browser, on the demo or a live page:
//   * the magnifier's search finds data: "pricing" lists /pricing/, Enter opens
//     Pages with its detail drawer (dd=path:/pricing/)
//   * every row about a value opens it, the whole row: a click on its number, Enter,
//     and the same in a data grid; the drawer's "go to" row and a visit's pages link on
//   * Back: closing the drawer steps out of its steps, and Back then leaves the tab
//     as it was before (the previous tab and filters)
//   * Insights: the five biggest, "Show all N", every window can be picked (Today too)
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/navigate.mjs https://host/traffic/<site>/ [user:password]
//
// On the demo: python3 tools/demo.py OUT, serve OUT, pass .../traffic/example.com/

const args = process.argv.slice(2);
const [base, auth = ""] = args.filter((a) => !a.startsWith("--"));
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node navigate.mjs <page url> [user:password]"); process.exit(2); }

const fails = [];
const check = (ok, what) => { console.log(`${ok ? "ok  " : "FAIL"} ${what}`); if (!ok) fails.push(what); };
const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 },
  httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
const p = await ctx.newPage();
p.on("pageerror", (e) => check(false, `page error: ${e.message}`));
const hash = () => p.evaluate(() => decodeURIComponent(location.hash));
const drawerOpen = () => p.evaluate(() => !!document.querySelector("dialog.dd[open]"));
const settle = () => p.waitForTimeout(500);

// A sessions install sends the browser to its sign-in page: sign in there (as switcher.mjs does).
await p.goto(`${base}#overview/summary?range=30d`, { waitUntil: "networkidle" });
if (p.url().includes("/traffic-auth/login") && auth) {
  await p.fill("#email", auth.split(":")[0]);
  await p.fill("#password", auth.split(":").slice(1).join(":"));
  await p.click("#submit");
  await p.waitForURL((u) => !u.pathname.startsWith("/traffic-auth/"));
}

// ---- the search
await p.goto(`${base}#overview/summary?range=30d`, { waitUntil: "networkidle" });
await p.click(".kbd-btn");
await p.fill(".pal-in", "pricing");
const found = await p.$$eval(".pal-list li", (ls) => ls.map((l) => l.textContent));
check(found.some((t) => t.startsWith("/pricing/")), `"pricing" finds /pricing/ (${found.length} results)`);
check(!found.some((t) => /Nothing matches/.test(t)), "and never says Nothing matches");
await p.keyboard.press("Enter");
await settle();
check((await hash()).startsWith("#traffic/pages") && (await hash()).includes("dd=path:/pricing/"), `Enter opens Pages with the detail: ${await hash()}`);
check(await drawerOpen(), "the detail drawer is open");
const jumps = await p.$$eval("dialog.dd .dd-jump", (bs) => bs.map((x) => x.textContent));
check(["Its visits", "Its sources", "Page story"].every((w) => jumps.includes(w)), `the drawer links on: ${jumps.join(", ")}`);
check(await p.$$eval("dialog.dd .dd-trail button.dl", (x) => x.length) > 0, "a visit's pages are links to each page's detail");
await p.keyboard.press("Escape");
await settle();
check(!(await drawerOpen()) && !(await hash()).includes("dd="), "Escape closes it");
await p.goBack();
await settle();
check((await hash()).startsWith("#overview/summary"), `Back returns to the tab before: ${await hash()}`);

// ---- whole rows
await p.goto(`${base}#traffic/sources?range=7d`, { waitUntil: "networkidle" });
await settle();
const rows = await p.$$("tr.drow");
check(rows.length > 0, `Sources has rows that open their value (${rows.length})`);
await p.click("tr.drow >> nth=0 >> td >> nth=-1");
await settle();
check((await hash()).includes("dd=") && await drawerOpen(), "a click on the row's last cell opens its value");
await p.keyboard.press("Escape");
await settle();
await p.focus("tr.drow >> nth=1");
await p.keyboard.press("Enter");
await settle();
check(await drawerOpen(), "Enter on a focused row opens it");
await p.locator("dialog.dd li.drow").first().click();
await settle();
check((await hash()).includes("|"), "a line in the drawer narrows the trail");
await p.locator("dialog.dd .dw-head .btn", { hasText: "Back" }).click();
await settle();
check(!(await hash()).includes("|") && await drawerOpen(), "the drawer's Back steps out one");
await p.keyboard.press("Escape");
await settle();
await p.goBack();
await settle();
check(!(await hash()).includes("dd="), `Back after closing does not reopen it: ${await hash()}`);
await p.goto(`${base}#traffic/pages?range=30d`, { waitUntil: "networkidle" });
await settle();
// Every grid row with a value's link opens it (a folded "all others" row has none).
const gridRows = await p.$$eval(".sk-grid tbody tr", (trs) => { const withLink = trs.filter((t) => t.querySelector("button.dl")); return [withLink.length, withLink.filter((t) => t.classList.contains("drow") || t.tabIndex === 0).length]; });
check(gridRows[0] > 0 && gridRows[0] === gridRows[1], `every grid row with a value opens it (${gridRows[1]} of ${gridRows[0]})`);

// ---- Insights
await p.goto(`${base}#overview/insights`, { waitUntil: "networkidle" });
await settle();
const shownCards = () => p.$$eval(".ins-short", (x) => x.filter((c) => c.offsetParent !== null).length);
const top = await shownCards();
check(top > 0 && top <= 5, `at most five cards first (${top})`);
const today = await p.$('.ins-bar button:has-text("Today")');
check(today && !(await today.isDisabled()), "Today can be picked");
const all = await p.$(".ins-all");
if (all) {
  await all.click();
  check(await shownCards() > top, "Show all shows the rest");
}
await today.click();
await settle();
check(await p.$$eval(".ins-what", (x) => x[0]?.textContent || "").then((t) => /first time today/.test(t)), "Today says what it lists");

// ---- Crawl health: a crawler's drawer counts the tab's own window (cw), whatever the bar's period
await p.goto(`${base}#ai/crawl?range=today`, { waitUntil: "networkidle" });
await settle();
const chRow = await p.$$eval(".ch-tab table tbody tr", (trs) => {
  const tr = trs.find((t) => t.querySelector("button.dl"));
  if (!tr) return null;
  const heads = [...tr.closest("table").querySelectorAll("thead th")].map((x) => x.textContent.replace(/[▲▼↕]/g, "").trim());
  return { name: tr.cells[0].querySelector("button.dl")?.textContent.trim(), requests: Number(tr.cells[heads.indexOf("Requests")].textContent.replace(/\D/g, "")) };
});
if (chRow) {
  await p.click(`.ch-tab table tbody tr:has(button.dl:has-text("${chRow.name}")) button.dl`);
  await settle();
  const said = await p.$eval(".dd-own", (x) => x.textContent).catch(() => "");
  const all = Number((said.match(/([\d,]+) in all/) || [])[1]?.replace(/,/g, "") ?? NaN);
  check(/today so far is not recorded/.test(said) || all === chRow.requests, `the ${chRow.name} drawer adds up to its Crawl health row (${chRow.requests}): "${said}"`);
  await p.keyboard.press("Escape");
}

await b.close();
console.log(fails.length ? `navigate: ${fails.length} failed` : "navigate: all passed");
process.exit(fails.length ? 1 : 0);
