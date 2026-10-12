// Time zones. Every moment the app shows goes through here, in the zone the
// reader picked in the top bar: their own (the browser's), the site's (the
// zone days are cut in) or UTC. Days stay the site's days: history is stored
// per site-time day, so ranges and totals never move; hours of the day do.

let CHOICE = "local", SITE = "UTC";
const LOCAL = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { return "UTC"; } })();

export const CHOICES = ["local", "site", "utc"];
export function setZone(choice, siteTz) { CHOICE = CHOICES.includes(choice) ? choice : "local"; SITE = siteTz || "UTC"; }
export const zone = () => (CHOICE === "utc" ? "UTC" : CHOICE === "site" ? SITE : LOCAL);
export const siteZone = () => SITE;
export const city = (tz) => (tz === "UTC" ? "UTC" : String(tz).split("/").pop().replace(/_/g, " "));
// The reader's zone is the site's (or UTC is), so nothing needs saying or shifting.
export const sameAsSite = () => zone() === SITE;

export function choiceWords(c) {
  if (c === "local") return `Your time (${city(LOCAL)})`;
  if (c === "site") return `Site time (${city(SITE)})`;
  return "UTC";
}

const fmts = new Map();
function parts(t, tz) {
  const key = tz;
  if (!fmts.has(key)) fmts.set(key, new Intl.DateTimeFormat("en-US", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZoneName: "short" }));
  return Object.fromEntries(fmts.get(key).formatToParts(new Date(t)).map((p) => [p.type, p.value]));
}

// Minutes a zone is ahead of UTC at a moment.
function offsetMin(tz, t) {
  const p = parts(t, tz);
  return Math.round((Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - Math.floor(t / 1000) * 1000) / 60000);
}

/* A site-time wall clock ("2026-10-07T14:24", no offset, as journeys keep
   it) as an instant. Two passes settle the offset across a DST change. */
export function siteWall(str) {
  const m = /^(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d)(?::(\d\d))?)?/.exec(str || "");
  if (!m) return NaN;
  const guess = Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0));
  let t = guess - offsetMin(SITE, guess) * 60000;
  t = guess - offsetMin(SITE, t) * 60000;
  return t;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// An instant (ISO with an offset, a site wall clock, or ms) as the chosen zone sees it.
export function when(ts) {
  if (ts == null || ts === "") return null;
  const t = typeof ts === "number" ? ts : /[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? Date.parse(ts) : siteWall(ts);
  if (Number.isNaN(t)) return null;
  const p = parts(t, zone());
  return { t, day: `${p.year}-${p.month}-${p.day}`, hour: p.hour, minute: p.minute, second: p.second, label: p.timeZoneName,
    date: `${+p.day} ${MONTHS[+p.month - 1]}` };
}

/* "16:05 EDT"; seconds: "16:05:09"; date: "7 Oct 16:05"; label false: no zone. */
export function time(ts, { seconds = false, date = false, label = true } = {}) {
  const w = when(ts);
  if (!w) return "";
  return `${date ? `${w.date} ` : ""}${w.hour}:${w.minute}${seconds ? `:${w.second}` : ""}${label ? ` ${w.label}` : ""}`;
}
// The chosen zone's short name now ("EDT", "GMT+5:30", "UTC").
export const label = () => parts(Date.now(), zone()).timeZoneName;

/* (Kept for callers that need the zone's own clock face.) One site day's hours ({"00": n, ...}, site time) as the chosen zone's hours.
   Returns {byDay: {zoneDay: {hh: n}}, exact} - exact is false for a zone a
   half hour off the site's, where an hour cannot be split; then the site's
   own hours are kept and the caller says so. */
export function shiftDay(day, hours) {
  const out = {};
  if (!hours) return { byDay: out, exact: true };
  if (sameAsSite()) return { byDay: { [day]: { ...hours } }, exact: true };
  let exact = true;
  for (const [hh, v] of Object.entries(hours)) {
    const w = when(siteWall(`${day}T${hh}:00`));
    if (!w || w.minute !== "00") { exact = false; break; }
    const d = out[w.day] || (out[w.day] = {});
    d[w.hour] = (d[w.hour] || 0) + (v || 0);
  }
  return exact ? { byDay: out, exact } : { byDay: { [day]: { ...hours } }, exact: false };
}

// One day's hours folded onto the clock face of the chosen zone (for "by hour" totals).
export function shiftHours(day, hours) {
  const { byDay, exact } = shiftDay(day, hours);
  const flat = {};
  for (const hs of Object.values(byDay)) for (const [hh, v] of Object.entries(hs)) flat[hh] = (flat[hh] || 0) + v;
  return { hours: flat, exact };
}

/* The 24 hours of a site day as the chosen zone's clock shows their start:
   ["04", "05", ... "03"] for New York read in UTC, "09:30" for a half-hour
   zone. Each bar or cell stays one whole site hour - nothing is re-cut - only
   its label moves, so every figure is exact. */
export function hourLabels(day) {
  const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
  if (sameAsSite()) return hours;
  return hours.map((hh) => { const w = when(siteWall(`${day}T${hh}:00`)); return w ? (w.minute === "00" ? w.hour : `${w.hour}:${w.minute}`) : hh; });
}

// The sentence every period line carries when the reader's zone is not the site's.
export const daysNote = () => (sameAsSite() ? "" : `Days are counted midnight to midnight, ${city(SITE)} time.`);
