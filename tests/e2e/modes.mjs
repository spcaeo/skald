// The two global modes in the top bar (2.7.0, js/modes.js), in a real browser:
//   * "Today", the first choice of the period group (2.42; it was the "Today · Live"
//     switch), turns the period to Today (range=today) and Compare off; another period
//     brings Compare back on
//   * Compare is on by default (2.42, state.js defaultCmp): a whole-days period is set
//     against the period before with no cmp= in the address; turned off, cmp=off
//   * "Compare with…" offers the previous period, the same period last year and
//     a custom B; a choice made in Live mode leaves Live; "Turn compare off" ends it
//   * a tab that registers compare shows what A and B are (or why not); one that
//     does not has no Compare button and says "No compare on this tab" only when
//     compare was asked for in the address
//   * mode-compare.js cmpTable: A · B · ± under grouped headers (sort marks ▲▼↕ aside), rows only one
//     period has count 0 in the other, the CSV names each column, "Per day" divides
//   * no console error
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/modes.mjs https://host/traffic/<site>/ [user:password]
//
// Works on the demo too: python3 tools/demo.py OUT, serve OUT, pass .../traffic/example.com/

const args = process.argv.slice(2);
const [base, auth = ""] = args.filter((a) => !a.startsWith("--"));
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node modes.mjs <page url> [user:password]"); process.exit(2); }

const fails = [];
let where = "";
const check = (ok, what) => { if (!ok) { fails.push(`${where}: ${what}`); console.log(`FAIL ${where}: ${what}`); } };
const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 },
  httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
const p = await ctx.newPage();
p.on("console", (m) => { if (m.type() === "error") check(false, `console error ${m.text()}`); });
p.on("pageerror", (e) => check(false, e.message));
const params = () => p.evaluate(() => Object.fromEntries(new URLSearchParams(location.hash.split("?")[1] || "")));
const go = async (hash) => { await p.goto(`${base}#${hash}`, { waitUntil: "networkidle" }); await p.waitForTimeout(350); };
const click = async (sel) => { await p.locator(sel).first().click(); await p.waitForTimeout(350); };

where = "Today, in the period group";
const today = '.bar .bar-range .seg button:has-text("Today")';
await go("traffic/sources?range=7d&cmp=prev");
await click(today);
let q = await params();
// Today is the default period (2.10.1): the address leaves range=today out.
check((q.range === "today" || q.range === undefined) && !q.cmp, `on: range ${q.range}, cmp ${q.cmp}`);
check(await p.locator(`${today}[aria-pressed="true"] .pulse`).count() === 1, "on: Today is pressed, with its pulsing dot");
await click('.bar .bar-range .seg button:has-text("7 days")');
q = await params();
check(q.range === "7d" && !q.cmp, `7 days: range ${q.range}, compare by default (cmp ${q.cmp})`);
check((await p.locator(".bar .mode-cmp").getAttribute("aria-pressed")) === "true", "7 days: Compare is on by default");

where = "Compare with…";
await go("overview/summary?range=today");
await click(".bar .mode-cmp");
check(await p.locator(".mode-pop:visible").count() === 1, "the panel opens");
check(await p.locator(".mode-pop .mode-opt").count() === 2 && await p.locator(".mode-pop .mode-custom input[type=date]").count() === 2, "previous period, last year and a custom period are offered");
await click('.mode-pop .mode-opt:has-text("Same period last year")');
q = await params();
check(q.cmp === "year" && q.range === "7d", `a choice in Live mode leaves Live: cmp ${q.cmp}, range ${q.range}`);
check((await p.locator(".bar .mode-cmp").getAttribute("aria-pressed")) === "true", "the button is pressed");
await click(".bar .mode-cmp");
await p.locator(".mode-pop .mode-custom input").nth(0).fill("2026-08-01");
await p.locator(".mode-pop .mode-custom input").nth(1).fill("2026-08-20");
await click('.mode-pop .mode-custom button:has-text("Compare")');
q = await params();
check(q.cmp === "custom" && q.cb === "2026-08-01..2026-08-20", `custom: cmp ${q.cmp}, cb ${q.cb}`);
await click(".bar .mode-cmp");
await p.keyboard.press("Escape");
await p.waitForTimeout(200);
check(await p.locator(".mode-pop:visible").count() === 0, "Escape closes the panel");
check(await p.evaluate(() => document.activeElement?.classList.contains("mode-cmp")), "Escape gives the focus back to the button");

where = "the line at the top of a tab";
// A past period: Today, the default since 2.10.1, is never compared (checked below).
await go("site/health?range=30d&cmp=prev");
const line = await p.locator("#panel .mode-banner").first().textContent().catch(() => "");
check(/^A .+ against B .+/.test(line.trim()) || /Not compared/.test(line), `a tab that compares names A and B or why not ("${line.trim().slice(0, 80)}")`);
await go("traffic/time?range=7d&cmp=year");
check(/No compare on this tab/.test(await p.locator("#panel .cmp-none").first().textContent().catch(() => "")), "a tab that does not compare says so when compare was asked for");
check(await p.locator(".bar .mode-cmp").count() === 0, "a tab that does not compare has no Compare button");
await go("traffic/time?range=7d");
check(await p.locator("#panel .cmp-none").count() === 0, "compare on by default: a tab that does not compare says nothing");
await go("overview/summary?range=today&cmp=prev");
check(/never compared/.test(await p.locator("#panel .mode-banner").first().textContent().catch(() => "")), "Live and Compare together: today is never compared");
await go("site/health?range=30d");
await click(".bar .mode-cmp");
await click(".mode-pop .mode-off");
q = await params();
check(q.cmp === "off", `Turn compare off on a compared period: cmp ${q.cmp}`);

where = "cmpTable";
const got = await p.evaluate(async () => {
  const M = await import(new URL("../_app/js/mode-compare.js", location.href).href);
  const T = await import(new URL("../_app/js/table.js", location.href).href);
  const c = { ok: true, perDay: false, used: { a: 30, b: 15 }, a: { first: "2026-09-01", last: "2026-09-30" }, b: { first: "2026-08-02", last: "2026-08-16" } };
  const cols = [{ key: "k", label: "Source" }, { key: "v", label: "Visitors", num: true }, { key: "sh", label: "Share", num: true }];
  const A = [{ k: "Search", v: 120, sh: 96 }, { k: "Email", v: 5, sh: 4 }], B = [{ k: "Search", v: 100, sh: 93 }, { k: "Social", v: 7, sh: 7 }];
  const read = (t) => ({
    groups: [...t.querySelectorAll("tr.grp-row th")].map((x) => [x.textContent, x.colSpan]),
    heads: [...t.querySelectorAll("thead tr:last-child th")].map((x) => x.textContent.replace(/[▲▼↕]/g, "")),
    rows: [...t.querySelectorAll("tbody tr")].map((tr) => [...tr.cells].map((td) => td.textContent.replace(/ \((up|down)\)/, ""))),
    csv: T.csv(T.REGISTRY.at(-1).columns, T.REGISTRY.at(-1).rows()).split("\r\n")[0],
    wide: t.classList.contains("cmp-tbl"),
  });
  const one = read(M.cmpTable(cols, A, B, { caption: "Sources", file: "s.csv", measures: ["v"] }, c));
  const per = read(M.cmpTable(cols, A, B, { caption: "Sources", file: "s.csv", measures: ["v"] }, { ...c, perDay: true }));
  return { one, per };
});
check(got.one.wide, "the table is a full-width compare table");
check(JSON.stringify(got.one.groups) === JSON.stringify([["", 1], ["Visitors", 3], ["", 1]]), `grouped headers ${JSON.stringify(got.one.groups)}`);
check(JSON.stringify(got.one.heads) === JSON.stringify(["Source", "A", "B", "±", "Share"]), `columns ${JSON.stringify(got.one.heads)}`);
check(JSON.stringify(got.one.rows) === JSON.stringify([["Search", "120", "100", "+20+20%", "96"], ["Email", "5", "0", "+5new", "4"], ["Social", "0", "7", "−7", "-"]]),
  `rows ${JSON.stringify(got.one.rows)}`);
check(got.one.csv === "Source,\"Visitors, A\",\"Visitors, B\",\"Visitors, change\",Share", `CSV header ${got.one.csv}`);
check(JSON.stringify(got.per.rows[0]) === JSON.stringify(["Search", "4", "6.7", "−2.7−40%"]).replace("]", ',"96"]'), `per day ${JSON.stringify(got.per.rows[0])}`);

await b.close();
console.log(fails.length ? `\n${fails.length} failed` : "modes: all passed");
process.exit(fails.length ? 1 : 0);
