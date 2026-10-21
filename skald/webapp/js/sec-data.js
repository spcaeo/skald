// Security's figures for a period (pure: no DOM). From security.json (security_page.py;
// docs/DATA-CONTRACT-SECURITY.md): each day's `security` blob, or null when the day kind was
// not counted ("not recorded", never 0). The tabs (js/tabs/sec-*.js) draw what this returns.
//
//   periodOf(f, r)       the period's days: those with figures, those without, today's
//   sumOf(blobs)         every figure summed over the days (the per-day tops summed, said so)
//   verdictOf(total)     "Is anything exposed?" in one line: ok, bad (possible exposures),
//                        warn (can't tell: no sizes), none (no scanner answered 2xx)
//   merge(rows, ans)     the suspect rows joined to the addresses (people/security), one row
//                        per address and agent when known, else per day and row number
//   blockList(rows, mode) the worst addresses (probes, then attack attempts) and networks
//   nginx / cloudflare / plain   the block list as text to download

export const FOLD = "(all others)";
export const STATUS = ["2xx", "3xx", "4xx", "5xx"];
export const ATTACK = (r) => (r.login || 0) + (r.burst || 0) + (r.injection || 0);

const add = (into, from) => { for (const [k, v] of Object.entries(from || {})) into[k] = (into[k] || 0) + (v || 0); return into; };

/* The period's days. r: {kind: "today"|"history", first, last}. */
export function periodOf(f, r) {
  if (!f) return { blobs: [], missing: [], days: 0 };
  if (r.kind === "today") {
    const b = f.today?.security || null;
    return { blobs: b ? [[f.today?.day || r.first, b]] : [], missing: b ? [] : [r.first], days: 1, today: true };
  }
  const blobs = [], missing = [];
  let days = 0;
  for (const d of f.days || []) {
    if (d.day < r.first || d.day > r.last) continue;
    days += 1;
    if (d.security) blobs.push([d.day, d.security]);
    else missing.push(d.day);
  }
  // Days the file does not list at all (before history, not collected) are missing too.
  const listed = new Set((f.days || []).map((d) => d.day));
  for (let d = r.first; d <= r.last; d = next(d)) if (!listed.has(d)) { missing.push(d); days += 1; }
  missing.sort();
  return { blobs, missing, days };
}

function next(iso) { const t = new Date(`${iso}T00:00:00Z`); t.setUTCDate(t.getUTCDate() + 1); return t.toISOString().slice(0, 10); }

export function sumOf(blobs) {
  const t = { days: blobs.length, probes: 0, probes_other: 0, scanners: 0, addresses: 0, requests: 0, forged: 0, bare_ip: 0,
    hosting: null, categories: {}, status: {}, countries: {}, paths: {}, perDay: [],
    exposure: { answered: 0, shell: 0, empty: 0, possible: 0, unknown: 0, folded: 0, rows: [], hosts: {} },
    injection: { requests: 0, kinds: {}, rows: [] }, login: { posts: 0, episodes: 0, rows: [] }, bursts: { requests: 0, episodes: 0, rows: [] },
    fake: { requests: 0, pairs: 0, kinds: {}, pages: {} }, who: [], whoDays: 0, whoFolded: 0 };
  for (const [day, b] of blobs) {
    for (const k of ["probes", "probes_other", "scanners", "addresses", "requests", "forged", "bare_ip"]) t[k] += b[k] || 0;
    if (b.hosting != null) t.hosting = (t.hosting || 0) + b.hosting;
    add(t.categories, b.categories); add(t.status, b.status); add(t.countries, b.countries); add(t.paths, b.paths);
    t.perDay.push({ day, probes: b.probes || 0, scanners: b.scanners || 0 });
    const e = b.exposure || {};
    for (const k of ["answered", "shell", "empty", "possible", "unknown", "folded"]) t.exposure[k] += e[k] || 0;
    for (const row of e.rows || []) t.exposure.rows.push({ ...row, day });
    for (const [host, x] of Object.entries(e.hosts || {})) {
      const h = t.exposure.hosts[host] || (t.exposure.hosts[host] = { host, bare_ip: !!x.bare_ip, answered: 0, shell: 0, empty: 0, possible: 0, unknown: 0, sizes: [] });
      for (const k of ["answered", "shell", "empty", "possible", "unknown"]) h[k] += x[k] || 0;
      if (x.shell_size != null && !h.sizes.includes(x.shell_size)) h.sizes.push(x.shell_size);
    }
    const a = b.attacks || {};
    t.injection.requests += a.injection?.requests || 0; add(t.injection.kinds, a.injection?.kinds);
    for (const row of a.injection?.rows || []) t.injection.rows.push({ ...row, day });
    for (const [name, unit] of [["login", "posts"], ["bursts", "requests"]]) {
      t[name][unit] += a[name]?.[unit] || 0; t[name].episodes += a[name]?.episodes || 0;
      for (const row of a[name]?.rows || []) t[name].rows.push({ ...row, day });
    }
    t.fake.requests += b.fake?.requests || 0; t.fake.pairs += b.fake?.pairs || 0; add(t.fake.kinds, b.fake?.kinds); add(t.fake.pages, b.fake?.pages);
    if (b.who_kept !== false && Array.isArray(b.who)) {
      t.whoDays += 1;
      t.whoFolded += b.who_folded || 0;
      for (const row of b.who) t.who.push({ ...row, day });
    }
  }
  return t;
}

/* The headline verdict of "Is anything exposed?". */
export function verdictOf(t) {
  const e = t.exposure;
  if (!t.days) return { tone: "none", words: "Not recorded for this period", n: 0 };
  if (e.possible) return { tone: "bad", words: `${e.possible} possible exposure${e.possible === 1 ? "" : "s"}: check ${e.possible === 1 ? "it" : "these"} now`, n: e.possible };
  if (e.unknown) return { tone: "warn", words: `Can't tell for ${e.unknown} answer${e.unknown === 1 ? "" : "s"}: the log has no size`, n: e.unknown };
  return { tone: "ok", words: e.answered ? "Nothing exposed in this period" : "Nothing exposed: no scanner probe was answered with a page", n: 0 };
}

/* Join the suspect rows to their addresses. ans: the helper's people/security answer (null for
   a reader who may not see addresses). Rows with a known address merge by address and agent
   across days; the rest stay one row per day and number. */
export function merge(rows, ans) {
  const by = new Map((ans?.rows || []).map((x) => [`${x.day}|${x.seq}`, x]));
  const out = new Map();
  for (const r of rows) {
    const who = by.get(`${r.day}|${r.seq}`);
    const known = who && who.ip && who.ip !== "(removed)";
    const key = known ? `${who.ip}|${who.user_agent || ""}` : `${r.day}|${r.seq}`;
    let m = out.get(key);
    if (!m) {
      m = { key, ip: known ? who.ip : null, agent: known ? who.user_agent || "" : null, removed: who?.ip === "(removed)", days: [], refs: [],
        first: r.first, last: r.last, requests: 0, probes: 0, injection: 0, login: 0, burst: 0, fake_requests: 0, bare_ip: 0,
        categories: {}, status: {}, probe_status: {}, paths: {}, pages: {}, kinds: [], fake: r.fake || null, forged: false, country: r.country || null, hosting: r.hosting ?? null };
      out.set(key, m);
    }
    m.days.push(r.day); m.refs.push(`${r.day}#${r.seq}`);
    if (r.first < m.first) m.first = r.first;
    if (r.last > m.last) m.last = r.last;
    for (const k of ["requests", "probes", "injection", "login", "burst", "fake_requests", "bare_ip"]) m[k] += r[k] || 0;
    add(m.categories, r.categories); add(m.status, r.status); add(m.probe_status, r.probe_status); add(m.paths, r.paths); add(m.pages, r.pages);
    for (const k of r.kinds || []) if (!m.kinds.includes(k)) m.kinds.push(k);
    m.forged = m.forged || !!r.forged;
    if (!m.fake && r.fake) m.fake = r.fake;
    if (!m.country && r.country) m.country = r.country;
    if (m.hosting == null && r.hosting != null) m.hosting = r.hosting;
  }
  return [...out.values()].sort((a, b) => b.probes - a.probes || ATTACK(b) - ATTACK(a) || b.requests - a.requests || (a.first < b.first ? -1 : 1));
}

// ------------------------------------------------------------------ networks

function v6(ip) {
  const [head, tail = ""] = ip.split("::");
  const a = head ? head.split(":") : [], b = tail ? tail.split(":") : [];
  const fill = ip.includes("::") ? Array(8 - a.length - b.length).fill("0") : [];
  return [...a, ...fill, ...b].map((x) => parseInt(x || "0", 16));
}

/* The network an address sits in: /24 for IPv4, /48 for IPv6 (the same cut a site that keeps
   addresses shortened uses). "" for anything that is not an address. */
export function networkOf(ip) {
  const s = String(ip || "").trim();
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(s)) return `${s.split(".").slice(0, 3).join(".")}.0/24`;
  if (s.includes(":")) {
    const p = v6(s.toLowerCase());
    if (p.length !== 8 || p.some((x) => Number.isNaN(x))) return "";
    return `${p.slice(0, 3).map((x) => x.toString(16)).join(":")}::/48`;
  }
  return "";
}

/* The block list: {addresses: [{ip, probes, attacks, requests, country, hosting, days}],
   networks: [{cidr, addresses, probes, attacks}]}. mode "full": each address, and each
   network holding two or more of them; "short": the kept addresses are networks already,
   so only networks; "off": nothing. */
export function blockList(merged, mode) {
  if (mode !== "full" && mode !== "short") return { addresses: [], networks: [] };
  const by = new Map();
  for (const m of merged) {
    if (!m.ip || !(m.probes || ATTACK(m))) continue;
    const got = by.get(m.ip) || { ip: m.ip, probes: 0, attacks: 0, requests: 0, country: m.country, hosting: m.hosting, days: new Set() };
    got.probes += m.probes; got.attacks += ATTACK(m); got.requests += m.requests;
    for (const d of m.days) got.days.add(d);
    by.set(m.ip, got);
  }
  const rank = (a, b) => b.probes - a.probes || b.attacks - a.attacks || b.requests - a.requests || (a.ip || a.cidr).localeCompare(b.ip || b.cidr);
  const addresses = [...by.values()].map((x) => ({ ...x, days: x.days.size })).sort(rank);
  const nets = new Map();
  for (const a of addresses) {
    const cidr = networkOf(a.ip);
    if (!cidr) continue;
    const got = nets.get(cidr) || { cidr, addresses: 0, probes: 0, attacks: 0, requests: 0 };
    got.addresses += 1; got.probes += a.probes; got.attacks += a.attacks; got.requests += a.requests;
    nets.set(cidr, got);
  }
  const networks = [...nets.values()].filter((x) => mode === "short" || x.addresses >= 2).sort(rank);
  return { addresses: mode === "short" ? [] : addresses, networks };
}

// ------------------------------------------------------------------ exports

const what = (x) => `${x.probes} probe${x.probes === 1 ? "" : "s"}${x.attacks ? `, ${x.attacks} attack attempt${x.attacks === 1 ? "" : "s"}` : ""}`;
const entries = (list) => [...list.networks.map((x) => ({ value: x.cidr, x })), ...list.addresses.map((x) => ({ value: x.ip, x }))];

/* nginx: one `deny` line per network and address, inside a server or http block. */
export function nginx(list, { site = "", first = "", last = "" } = {}) {
  const head = [`# Skald block list${site ? ` for ${site}` : ""}${first ? `, ${first} to ${last}` : ""}.`,
    "# Review before you use it: a shared address or a CDN can carry real visitors too.",
    "# Put these lines in the server { } block (or http { }), then: nginx -t && systemctl reload nginx"];
  return [...head, ...entries(list).map(({ value, x }) => `deny ${value};  # ${what(x)}`), ""].join("\n");
}

// ------------------------------------------------------------- log signs

/* "Worth a look" (never "attack detected"): a day of the period whose gateway errors (502,
   503, 504) or .php requests reach at least SIGN_FACTOR times the median of the
   SIGN_DAYS days before it that have the figure, and at least SIGN_MIN. With fewer than
   SIGN_NEED such days there is no usual to compare with, and nothing is flagged. */
export const SIGN_FACTOR = 3, SIGN_DAYS = 14, SIGN_NEED = 7, SIGN_MIN = 20;
const median = (xs) => { const v = [...xs].sort((a, b) => a - b); const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };

export function signsOf(f, r) {
  const days = (f?.days || []).filter((d) => d.security?.signs);
  const inPeriod = r.kind === "today" ? (f?.today?.security?.signs ? [{ day: r.first, security: f.today.security }] : [])
    : days.filter((d) => d.day >= r.first && d.day <= r.last);
  const rows = [];
  let posts = null;
  for (const d of inPeriod) {
    const before = days.filter((x) => x.day < d.day).slice(-SIGN_DAYS);
    for (const kind of ["gateway", "php"]) {
      const n = d.security.signs[kind]?.requests || 0;
      const usual = before.length >= SIGN_NEED ? median(before.map((x) => x.security.signs[kind]?.requests || 0)) : null;
      const peak = Object.entries(d.security.signs[kind]?.hours || {}).sort((a, b) => b[1] - a[1])[0] || null;
      if (usual != null && n >= SIGN_MIN && n >= SIGN_FACTOR * usual) rows.push({ day: d.day, kind, n, usual, peak });
    }
    const p = d.security.signs.posts;
    if (p) {
      posts = posts || { recorded: 0, large: 0, max: null, paths: {} };
      posts.recorded += p.recorded; posts.large += p.large;
      posts.max = posts.max == null ? p.max : Math.max(posts.max, p.max ?? 0);
      add(posts.paths, p.paths);
    }
  }
  return { rows, posts, days: inPeriod.length };
}

/* Cloudflare IP list CSV: one address or CIDR and a description per line, no header
   (Account > Manage account > Configurations > Lists > Upload CSV). */
export function cloudflare(list) {
  const q = (s) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
  return [...entries(list).map(({ value, x }) => `${value},${q(`Skald: ${what(x)}`)}`), ""].join("\n");
}

/* Plain: one address or CIDR per line (fail2ban, ipset, a firewall's import). */
export function plain(list) {
  return [...entries(list).map(({ value }) => value), ""].join("\n");
}
