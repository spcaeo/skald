// The browser half of tools/bench_load.py: open a site's Overview signed in, over a
// throttled line, cold, warm and after a site switch; then the Overview over 30 days (its
// page cards drawn) and Traffic > Pages (its leaderboard drawn); print one JSON line.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tools/bench_load.mjs https://127.0.0.1:PORT COOKIE site-a site-b [--repeat 3]

const args = process.argv.slice(2);
const flag = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const [base, cookie, siteA, siteB] = args.filter((a, i) => !a.startsWith("--") && !(i > 0 && args[i - 1].startsWith("--")));
const repeat = Number(flag("--repeat", "3"));
// The local certificate, trusted by its key: with ignoreHTTPSErrors instead, Chromium would keep
// nothing in its cache (a host whose certificate is in error), and warm loads would mean nothing.
const spki = flag("--spki", "");
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");

// About the owner's line on 2026-10-26 (15.4 MB in 5.7 s), with a 40 ms round trip.
const LINE = { offline: false, latency: Number(flag("--latency", "40")), downloadThroughput: 2.5e6, uploadThroughput: 1e6 };
// The key figures: the period's tiles, or Live mode's (the Overview opens on today).
const KPIS = "[aria-label='Key figures'] .t-v, .td-kpis .td-kv";

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };

// Done: the panel shows the text, and no part of it is still loading (lazy.js).
const drawn = (text) => (page) => page.waitForFunction((t) => {
  const p = document.getElementById("panel");
  return !!p && p.textContent.includes(t) && !p.querySelector(".lazy-wait");
}, text, { timeout: 120000, polling: 50 });

async function open(page, cdp, url, done = null, kpis = true) {
  const seen = new Map();
  let bytes = 0;
  const on = (name, fn) => { cdp.on(name, fn); return () => cdp.off(name, fn); };
  const offs = [
    on("Network.requestWillBeSent", (e) => { if (!e.request.url.startsWith("data:")) seen.set(e.requestId, { url: e.request.url, cache: false }); }),
    on("Network.requestServedFromCache", (e) => { const r = seen.get(e.requestId); if (r) r.cache = true; }),
    on("Network.responseReceived", (e) => { const r = seen.get(e.requestId); if (r && (e.response.fromDiskCache || e.response.fromPrefetchCache)) r.cache = true; if (r) r.status = e.response.status; }),
    on("Network.loadingFinished", (e) => { if (seen.has(e.requestId)) bytes += e.encodedDataLength || 0; }),
  ];
  // From another page, so an address that differs only after "#" is a whole new load.
  await page.goto("about:blank");
  const t0 = Date.now();
  await page.goto(url, { waitUntil: "commit" });
  // Traffic > Pages has no key figures: its leaderboard is what it waits for.
  if (kpis) await page.waitForSelector(KPIS, { state: "visible", timeout: 120000 });
  const atKpis = kpis ? await page.evaluate(() => performance.now()) : null;
  let ready = null;
  if (done) { await done(page); ready = await page.evaluate(() => performance.now()); }
  await page.waitForLoadState("networkidle", { timeout: 120000 }).catch(() => {});
  const quiet = Date.now() - t0;
  offs.forEach((f) => f());
  const net = [...seen.values()].filter((r) => !r.cache);
  return { requests: net.length, bytes, kpis_ms: atKpis === null ? null : Math.round(atKpis), quiet_ms: quiet, ready_ms: ready === null ? null : Math.round(ready),
    not_modified: net.filter((r) => r.status === 304).length,
    data: net.filter((r) => /\/data\/[a-z_]+\.json/.test(r.url)).map((r) => r.url.replace(/^.*\/data\//, "")).sort() };
}

const b = await chromium.launch({ ...(process.env.CHROME ? { executablePath: process.env.CHROME } : {}),
  args: spki ? [`--ignore-certificate-errors-spki-list=${spki}`] : [] });
const runs = { cold: [], warm: [], switch: [], period: [], pages: [] };
for (let i = 0; i < repeat; i++) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: !spki });
  const host = new URL(base).hostname;
  await ctx.addCookies([{ name: "skald_session", value: cookie, domain: host, path: "/", secure: true, httpOnly: true, sameSite: "Lax" }]);
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", LINE);
  runs.cold.push(await open(page, cdp, `${base}/traffic/${siteA}/`));
  runs.warm.push(await open(page, cdp, `${base}/traffic/${siteA}/`));
  runs.switch.push(await open(page, cdp, `${base}/traffic/${siteB}/`));
  runs.period.push(await open(page, cdp, `${base}/traffic/${siteA}/#overview/summary?range=30d`, drawn("New and updated pages")));
  runs.pages.push(await open(page, cdp, `${base}/traffic/${siteA}/#traffic/pages?range=30d`, drawn("Page leaderboard"), false));
  if (errors.length) { console.error(`page errors: ${errors.join(" | ")}`); process.exitCode = 1; }
  await ctx.close();
}
await b.close();
const out = {};
for (const [k, list] of Object.entries(runs)) {
  out[k] = { requests: median(list.map((r) => r.requests)), bytes: median(list.map((r) => r.bytes)),
    kpis_ms: list[0].kpis_ms === null ? null : median(list.map((r) => r.kpis_ms)), quiet_ms: median(list.map((r) => r.quiet_ms)),
    ready_ms: list[0].ready_ms === null ? null : median(list.map((r) => r.ready_ms)),
    not_modified: median(list.map((r) => r.not_modified)), data: list[0].data };
}
console.log(JSON.stringify(out));
