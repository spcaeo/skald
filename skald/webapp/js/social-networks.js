// Social networks as the page reads them (social_networks.py): the Social media visits by
// network (X, LinkedIn, Facebook, ...), counted, never inferred. Pure, no DOM
// (tests/js/social-networks.mjs). campaigns.json carries the day kind as
// days[].social_networks and today.social_networks, null on a day it was not recorded, and
// the networks' names and the method as social_networks.

// The names when campaigns.json has none (an older file): social_names.py's.
export const NAMES = { x: "X", linkedin: "LinkedIn", facebook: "Facebook", threads: "Threads", instagram: "Instagram",
  reddit: "Reddit", youtube: "YouTube", tiktok: "TikTok", pinterest: "Pinterest", bluesky: "Bluesky", mastodon: "Mastodon",
  hackernews: "Hacker News", quora: "Quora", telegram: "Telegram", whatsapp: "WhatsApp", slack: "Slack", discord: "Discord",
  other: "Social, network not named" };
export const OTHER = "other";
export const nameOf = (f, id) => f?.social_networks?.names?.[id] || NAMES[id] || id;
// A network id as the address may carry it: short, lower-case letters only.
export const isNetId = (v) => /^[a-z]{1,12}$/.test(String(v ?? ""));

// The days of a range: verified days only (a withheld day is left out), or today's.
// blobs: the days that recorded the figure; days: the verified days; missing: verified days
// recorded before it existed (shown as "over n of m days", never as zeros).
export function rangeBlobs(f, r) {
  if (!f || !r) return { blobs: [], days: 0, missing: 0, list: [] };
  const list = r.kind === "today" ? (f.today && f.today.state === "ok" ? [f.today] : [])
    : (f.days || []).filter((d) => d.state === "ok" && d.day >= r.first && d.day <= r.last);
  const blobs = list.map((d) => d.social_networks).filter(Boolean);
  return { blobs, days: list.length, missing: list.length - blobs.length, list };
}

const addTo = (into, obj) => { for (const [k, v] of Object.entries(obj || {})) into[k] = (into[k] || 0) + (v || 0); };
const sum = (o) => Object.values(o || {}).reduce((a, v) => a + (v || 0), 0);

// The blobs summed. `ok` is false when a sum the server promises does not hold: the page then
// withholds the figures rather than show ones that do not add up.
export function sumNetworks(blobs) {
  const t = { visits: 0, social: 0, networks: {}, via: {}, landings: {}, ok: true };
  for (const b of blobs || []) {
    t.visits += b.visits || 0; t.social += b.social || 0;
    addTo(t.networks, b.networks);
    for (const part of ["via", "landings"]) for (const [k, v] of Object.entries(b[part] || {})) addTo(t[part][k] || (t[part][k] = {}), v);
    const nets = b.networks || {};
    if (sum(nets) !== (b.social || 0) || (b.social || 0) > (b.visits || 0)) t.ok = false;
    for (const part of ["via", "landings"]) {
      const got = b[part] || {};
      if (Object.keys(got).sort().join() !== Object.keys(nets).sort().join()) t.ok = false;
      for (const [k, v] of Object.entries(nets)) if (sum(got[k]) !== v) t.ok = false;
    }
  }
  return t;
}

// One network's visitors on each of a range's days (null on a day not recorded), for "Per day".
export function perDay(f, r, id) {
  if (!f || !r || r.kind !== "history") return [];
  const byDay = new Map((f.days || []).map((d) => [d.day, d]));
  const out = [];
  for (const d of r.days || []) {
    const e = byDay.get(d.day);
    out.push(e && e.state === "ok" && e.social_networks ? e.social_networks.networks?.[id] || 0 : null);
  }
  return out;
}

// How a visit was matched, in words: a host as it is, an app, or a tag.
const TAGS = { "(utm_source)": "a link tagged utm_source", "(utm_medium)": "a link tagged utm_medium",
  "(fbclid)": "an ad click id (fbclid)", "(li_fat_id)": "an ad click id (li_fat_id)", "(ttclid)": "an ad click id (ttclid)",
  "(twclid)": "an ad click id (twclid)", "(none)": "no referrer or tag" };
export function viaWords(how) {
  const v = String(how ?? "");
  if (TAGS[v]) return TAGS[v];
  if (v.startsWith("android-app://")) return `the Android app ${v.slice("android-app://".length)}`;
  return v;
}
// A host's own address, for copy and open; an app or a tag has none.
export const viaHref = (how) => (/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(String(how ?? "")) ? `https://${how}` : "");

// The method in one sentence.
export function method(f) {
  return f?.social_networks?.method || "Counted, not inferred: each Social media visit gets one network, by its referring host or app, else by the words of its utm_source or utm_medium, else by a social ad click id. The networks add up to the Social media row.";
}
