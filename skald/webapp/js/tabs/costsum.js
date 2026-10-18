// What each crawler costs, summed over a range (crawler_cost.json). No DOM
// here, so node can test the sums (tests/test_crawler_cost.py).
//
// The honesty rules, as data.js keeps them for every other figure:
//   * only verified ("ok") days are summed; a day without the figure (collected
//     before it existed) is counted in `unrecorded`, never added in as zero
//   * requests, bytes and the lines behind them are summed; bytes stay null
//     (not recorded) when no line of the range had a size, and a sum over
//     fewer lines than requests is `partial`
//   * the mean response time is weighted by request: all milliseconds over
//     all timed lines. The p90 is a single day's (or today's) only: a range's
//     p90 cannot be built from daily ones, so it is null for longer ranges
//   * distinct paths are counted per day; over a range they are summed, so a
//     path fetched on two days counts twice, and re-crawl is requests per
//     distinct path within a day

export const OTHER = "(all others)";

// The days of a range that hold the file's figures: [[day, names], ...] and how many have none.
export function daysOf(file, r) {
  if (!file) return { used: [], unrecorded: 0 };
  if (r.kind === "today") {
    const t = file.today;
    return t && t.names ? { used: [[t.day || "today", t.names]], unrecorded: 0 } : { used: [], unrecorded: t ? 1 : 0 };
  }
  const used = [];
  let unrecorded = 0;
  for (const d of file.days || []) {
    if (d.state !== "ok" || d.day < r.first || d.day > r.last) continue;
    if (d.names) used.push([d.day, d.names]);
    else unrecorded += 1;
  }
  return { used, unrecorded };
}

const add = (a, b) => (b == null ? a : (a || 0) + b);

/* One row per (group, name) over the range. `keep(group, name, row)`
   chooses the names (a tab shows some groups, or one tier). */
export function sumCosts(file, r, keep = () => true) {
  const { used, unrecorded } = daysOf(file, r);
  const rows = new Map();
  for (const [, names] of used) {
    for (const [group, byName] of Object.entries(names)) {
      for (const [name, e] of Object.entries(byName)) {
        if (!keep(group, name, e)) continue;
        const k = `${group}\u0000${name}`;
        const a = rows.get(k) || { group, name, tier: e.tier || null, folded: name === OTHER, requests: 0, bytes: null, sized: 0, ms: null, timed: 0, p90: null,
          status: {}, paths: 0, pathsKnown: true, last: null, days: 0 };
        a.requests += e.requests || 0;
        a.bytes = add(a.bytes, e.bytes);
        a.sized += e.sized || 0;
        a.ms = add(a.ms, e.ms);
        a.timed += e.timed || 0;
        a.p90 = e.p90_ms ?? null;
        for (const [c, v] of Object.entries(e.status || {})) a.status[c] = (a.status[c] || 0) + v;
        if (e.paths == null) a.pathsKnown = false;
        else a.paths += e.paths;
        if (e.last && (!a.last || e.last > a.last)) a.last = e.last;
        a.days += 1;
        rows.set(k, a);
      }
    }
  }
  const single = used.length === 1;
  const out = [...rows.values()].map((a) => {
    const errors = (a.status["4xx"] || 0) + (a.status["5xx"] || 0);
    const paths = a.pathsKnown ? a.paths : null;
    return {
      group: a.group, name: a.name, tier: a.tier, folded: a.folded, days: a.days,
      requests: a.requests,
      bytes: a.sized ? a.bytes : null, sized: a.sized, partial: a.sized > 0 && a.sized < a.requests,
      mean_ms: a.timed ? a.ms / a.timed : null, timed: a.timed,
      p90_ms: single && !a.folded ? a.p90 : null,
      status: a.status, errors, error_share: a.requests ? errors / a.requests : null,
      paths, recrawl: paths ? a.requests / paths : null, last: a.last,
    };
  });
  out.sort((x, y) => y.requests - x.requests || (x.name < y.name ? -1 : 1));
  return { rows: out, days: used.length, unrecorded, single };
}

/* One name over the range, every group it was seen in: requests per day,
   and its pages, countries and agents from the days that keep them. */
export function detailOf(file, r, name) {
  const { used, unrecorded } = daysOf(file, r);
  const perDay = new Map();
  const lists = { pages: {}, countries: {}, agents: {} };
  const status = {};
  // agentsHidden: a bot whose strings may be a person's browser; they are not kept.
  let listed = 0, last = null, agentsHidden = false;
  for (const [day, names] of used) {
    let seen = false, hasLists = false;
    for (const byName of Object.values(names)) {
      const e = byName[name];
      if (!e) continue;
      seen = true;
      perDay.set(day, (perDay.get(day) || 0) + (e.requests || 0));
      for (const [c, v] of Object.entries(e.status || {})) status[c] = (status[c] || 0) + v;
      if (e.last && (!last || e.last > last)) last = e.last;
      if (e.pages) {
        hasLists = true;
        if (e.agents == null) agentsHidden = true;
        for (const key of Object.keys(lists)) for (const [k, v] of Object.entries(e[key] || {})) lists[key][k] = (lists[key][k] || 0) + v;
      }
    }
    // Not listed that day: none, unless a group folded names into its tail (it may be there).
    if (!seen) perDay.set(day, Object.values(names).some((g) => g[OTHER]) ? null : 0);
    if (hasLists) listed += 1;
  }
  return { perDay, status, lists, listed, last, agentsHidden, days: used.length, unrecorded };
}

// Bytes in words: 1,234 B, 12.3 KB, 4.5 MB (1 KB = 1,000 bytes).
export function bytesWords(v) {
  if (v == null) return "not recorded";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let x = v, i = 0;
  while (x >= 1000 && i < units.length - 1) { x /= 1000; i += 1; }
  return i ? `${x.toFixed(x < 10 ? 1 : 0)} ${units[i]}` : `${Math.round(x)} B`;
}
