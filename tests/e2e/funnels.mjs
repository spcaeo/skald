// Funnels: a step written in the link reads back the same; a visit counts at a
// step only when it saw the steps before it, in order, by the server's rules; the chart's figures
// match a count made here from the same journeys; a step opens its visits.
//
//   PLAYWRIGHT=/path/to/node_modules/playwright/index.mjs \
//   node tests/e2e/funnels.mjs https://host/traffic/<site>/ [user:password]

const [base, auth = ""] = process.argv.slice(2);
const { chromium } = await import(process.env.PLAYWRIGHT || "playwright");
if (!base) { console.error("usage: node funnels.mjs <page url> [user:password]"); process.exit(2); }
const fails = [];
const fail = (what) => { fails.push(what); console.log(`FAIL ${what}`); };

const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 },
  httpCredentials: auth ? { username: auth.split(":")[0], password: auth.split(":").slice(1).join(":") } : undefined });
const p = await ctx.newPage();
p.on("pageerror", (e) => fail(`page error: ${e.message}`));
await p.goto(`${base}#funnels?range=today`, { waitUntil: "networkidle" });

const unit = await p.evaluate(async () => {
  const F = await import(new URL("../_app/js/tabs/funnels.js", location.href).href);
  const out = [];
  for (const g of ["*", "/pricing/", "/blog/*", "~demo", "* > /pricing/ > ~signup", "/a/|/b/", "* > /pricing/ > lead:signup,contact", "*demo*", "* > event:cta_click"]) if (F.glob(F.parse(g)) !== g) out.push(`"${g}" reads back as "${F.glob(F.parse(g))}"`);
  const j = { trail: [{ path: "/" }, { path: "/features/" }, { path: "/pricing/" }, { path: "/signup/" }] };
  // The server's rules (funnels.py): the page that met one step may meet the next; "is" ignores a last slash.
  const cases = [["* > /pricing/ > /signup/", 3], ["/pricing/ > /features/", 1], ["/features/* > ~signup", 2], ["/nope/", 0], ["* > *", 2],
    ["* > /", 2], ["* > /nope/", 1], ["/pricing > /pricing/", 2], ["/x/|/signup/", 1], ["~PRICING", 1], ["*sign*", 1], ["/ > *ric*", 2]];
  for (const [g, want] of cases) { const got = F.reached(j, F.parse(g)); if (got !== want) out.push(`"${g}" reached ${got}, not ${want}`); }
  return out;
});
for (const u of unit) fail(u);

// The chart against a count of the same journeys, made here.
await p.goto(`${base}#funnels?range=today&fn=${encodeURIComponent("* > /pricing*")}`, { waitUntil: "networkidle" });
await p.waitForTimeout(300);
const got = await p.evaluate(async () => {
  const shown = [...document.querySelectorAll(".fn-v b")].map((b) => Number(b.textContent.replace(/\D/g, "")));
  const res = await fetch("data/visits.json"); const v = await res.json();
  const js = (v.today?.journeys || []);
  const start = js.length, priced = js.filter((j) => j.trail.some(([path]) => path.split("?")[0].startsWith("/pricing"))).length;
  return { shown, start, priced };
});
if (got.shown.length) {
  if (got.shown[0] !== got.start) fail(`step 1 shows ${got.shown[0]}, today's journeys are ${got.start}`);
  if (got.shown[1] !== got.priced) fail(`step 2 shows ${got.shown[1]}, journeys that saw a pricing page are ${got.priced}`);
  // A step opens its visits.
  await p.locator(".fn-bar").nth(1).click();
  await p.waitForTimeout(300);
  const listed = await p.evaluate(() => Number(document.querySelector(".fn-count")?.textContent.replace(/\D/g, "") || -1));
  if (listed !== got.priced) fail(`step 2 lists ${listed} visits, not ${got.priced}`);
} else if (got.start) fail("no chart, though today has journeys");

await b.close();
console.log(fails.length ? `${fails.length} failed` : "funnels: all passed");
process.exit(fails.length ? 1 : 0);
