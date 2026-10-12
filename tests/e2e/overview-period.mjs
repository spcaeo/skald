// Overview follows the date range: switching Today -> 7 days -> 30 days must
// change what the page reports, or say honestly why it cannot.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/overview-period.mjs https://host/traffic/<site>/ [user:password]
//
// Not part of the Python suite (it needs a browser and a served page).
// For each range it reads the period line, the tiles (seven since 2.5.0: leads and demos booked) and the "how these
// numbers relate" line, and checks:
//   * the period line names that range, and changes with it
//   * a range with no whole day shows the empty state, never a row of zeros
//   * a range with some days missing shows the period banner
//   * nothing on the page says "today" unless the range is Today
//   * when two ranges both have figures, the relate line differs
//   * no console error and no failed request under the page's own CSP

const [, , base, auth = ""] = process.argv;
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node overview-period.mjs <page url> [user:password]"); process.exit(2); }

const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 },
  httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
const p = await ctx.newPage();
const errors = [];
p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
p.on("pageerror", (e) => errors.push(e.message));
p.on("requestfailed", (r) => errors.push(`failed ${r.url()}`));

const fails = [];
const check = (ok, what) => { if (!ok) fails.push(what); console.log(`${ok ? "ok  " : "FAIL"} ${what}`); };
const seen = [];
for (const [range, words] of [["today", /^Today/], ["yesterday", /^\w{3} \d+ \w{3} \d{4}/], ["7d", /Last 7 whole days|^\w{3} \d/], ["30d", /Last 30 whole days/]]) {
  await p.goto(`${base}#overview?range=${range}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(400);
  const got = await p.evaluate(() => ({
    period: document.querySelector("#panel .head .period")?.textContent.trim() || "",
    tiles: [...document.querySelectorAll("#panel .tile")].map((t) => [t.querySelector(".t-l")?.textContent, t.querySelector(".t-v")?.textContent]),
    relate: document.querySelector("#panel .relate")?.textContent || "",
    banner: !!document.querySelector("#panel .period-banner"),
    empty: !!document.querySelector("#panel .state"),
    // The page's words, without its buttons (an offer to "Show today so far" is not a figure).
    text: [...document.getElementById("panel").querySelectorAll("p, span, div, h1, h2, h3, li, td")].filter((e) => !e.closest("button") && !e.children.length).map((e) => e.textContent).join(" "),
  }));
  check(words.test(got.period), `${range}: the period line names the range ("${got.period}")`);
  check(!seen.some((x) => x.period === got.period), `${range}: the period line differs from the ranges before`);
  if (!got.tiles.length) check(got.empty, `${range}: no figures, so the empty state explains why`);
  else check(!got.tiles.every(([, v]) => v === "0"), `${range}: the tiles are not a row of bare zeros`);
  const partial = / whole days? recorded, \d+ not/.test(got.period);
  if (partial && got.tiles.length) check(got.banner, `${range}: some days missing, so the banner says what the totals cover`);
  if (range !== "today") check(!/today so far|so far today/i.test(got.text), `${range}: nothing on the page is silently today-only`);
  for (const prev of seen) if (prev.relate && got.relate) check(prev.relate !== got.relate, `${range}: the figures differ from ${prev.range}'s`);
  seen.push({ ...got, range });
}
check(!errors.length, `no console error or failed request${errors.length ? `: ${errors.join("; ")}` : ""}`);
await b.close();
console.log(fails.length ? `\n${fails.length} failed` : "\nall passed");
process.exit(fails.length ? 1 : 0);
