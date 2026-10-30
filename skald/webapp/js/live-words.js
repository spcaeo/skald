// Live status, as data (2.44): the timing and the plain words of every "connect" journey's
// live state and its Test button. No DOM here, so node runs it (tests/js/live.mjs). The pieces
// that draw it are js/ui/live.js; the server's answer is skald/connect_check.py
// (POST <page>/sites/arrived).
//
// The owner (2026-10-27), on one site's Traffic › Search: he connected Search Console, the
// 16-month history was syncing, and the open page still said "Search Console is not connected
// yet". The page decided from its built file, fetched once. Now a page that shows a
// connection's state asks the helper for the live state, words it for a person who is not
// technical, and reads its data file again once the live state moved past it.

// How often a page asks: every 5 s for the first 3 minutes, then every 30 s; never while the
// tab is hidden or once the piece left the page. A viewer (who may not ask the helper) reads
// the built file again once a minute while it says something is in progress.
export const POLL = { every: 5000, slowAfter: 180000, slow: 30000 };
export const delay = (elapsed, p = POLL) => (elapsed < p.slowAfter ? p.every : p.slow);
export const VIEWER_EVERY = 60000;
// A page reads its data files again at most this often while the live state is ahead of them.
export const REDRAW_GAP = 20000;

const n = (x) => Number(x || 0).toLocaleString("en-GB");
const hm = (iso) => (iso ? String(iso).slice(11, 16) : "");

/* A test's answer box kind: ok, wait or bad. */
export const kindOf = (verdict) => (verdict === "ok" ? "ok" : verdict === "bad" ? "bad" : "warn");
/* The pill for a verdict: [kind, words]. */
export function pillOf(verdict) {
  if (verdict === "ok") return ["good", "Working"];
  if (verdict === "bad") return ["bad", "Needs a fix"];
  if (verdict === "wait") return ["warn", "Waiting"];
  return ["off", "Not checked yet"];
}

// ------------------------------------------------------------------ Search
const TOOL = { google: "Search Console", bing: "Bing Webmaster Tools" };
const WHOSE = { google: "Google's", bing: "Bing's" };

/* One engine's live state from GET integrations/search (engines[e]: connected, status,
   summary, busy), in plain words: {state, pill, words, busy}. state: off, syncing,
   failing, waiting (connected, no figures yet), connected. */
export function searchState(part, engine = "google") {
  const tool = TOOL[engine] || TOOL.google;
  if (!part || !part.connected) return { state: "off", pill: ["off", "Not connected"], words: `${tool} is not connected yet.`, busy: false };
  const st = part.status || {};
  const sum = part.summary || {};
  const b = st.backfill;
  const days = Number(sum.days || 0);
  if (b && (b.state === "running" || b.state === "queued")) {
    const of = Number(b.of || 0);
    const got = of ? `${n(b.done || 0)} of ${n(of)} weeks` : "starting";
    return { state: "syncing", pill: ["info", "Syncing"], busy: true,
      words: `Connected. Getting ${WHOSE[engine] || "the engine's"} history: ${got}.${days ? ` ${n(days)} days are here so far.` : " The figures appear as each week arrives."}` };
  }
  if (st.error) return { state: "failing", pill: ["bad", "Sync failing"], busy: false, tech: st.error,
    words: `Connected, but the last sync failed.${days ? ` The ${n(days)} days already here stay.` : ""} Open Search Console & Bing in Settings to fix it.` };
  if (!days) {
    const first = !st.last_sync;
    return { state: "waiting", pill: ["warn", "Waiting for figures"], busy: first || !!part.busy,
      words: first ? "Connected. The first figures arrive with the first sync, usually within a few minutes."
        : `Connected and synced, but ${tool} has no figures for this site yet. Google starts a new property's figures a few days after it is verified.` };
  }
  return { state: "connected", pill: ["good", "Connected"], busy: !!part.busy,
    words: `Connected. ${n(days)} days of ${tool}'s figures are here${sum.last ? `, the newest ${sum.last}` : ""}.` };
}

/* Is the live answer ahead of the page's built file? (Then the page reads its file again.)
   file, live: the same engine's part, from search.json and from GET integrations/search. */
export function searchAhead(file, live) {
  if (!live) return false;
  if (!!live.connected !== !!file?.connected) return true;
  if (!live.connected) return false;
  const fd = Number(file?.summary?.days || 0), ld = Number(live.summary?.days || 0);
  if (ld > fd) return true;
  const fb = file?.status?.backfill, lb = live.status?.backfill;
  if ((lb?.state || "") !== (fb?.state || "") || Number(lb?.done || 0) > Number(fb?.done || 0)) return true;
  return (live.status?.last_sync || "") > (file?.status?.last_sync || "");
}

/* Does the built file say something is still in progress? (A viewer then reads it again.) */
export function searchBusy(file) {
  for (const part of Object.values(file?.engines || {})) {
    const b = part?.status?.backfill;
    if (part?.connected && (b?.state === "running" || b?.state === "queued" || (!part.summary?.days && !part.status?.last_sync))) return true;
  }
  return false;
}

// ------------------------------------------------------------------ Test answers
/* The words under a test's head: the agent's progress (opened, keys taken, reported), when
   Skald knows it. steps: [{id, words, done, at}] from sites/arrived. */
export function stepLines(steps) {
  return (steps || []).map((s) => ({ id: s.id, words: s.words, done: !!s.done, at: s.at || null }));
}

/* "Last checked 10:42", with the moment the answer was made (UTC ISO). */
export const checkedAt = (iso, clock = hm) => (iso ? `Last checked ${clock(iso)}.` : "");

/* The plain words of a hook's live state (GET integrations tools[]: state, last_at, test_at),
   for a page that shows a webhook address. */
export function hookWords(t, name) {
  if (!t) return { verdict: null, words: "" };
  // 2.44.1: real deliveries refused since the key was saved, and none accepted: never "Connected".
  const s = t.set !== false && t.since_saved && typeof t.since_saved === "object" ? t.since_saved : null;
  if (s && !Number(s.accepted || 0) && (Number(s.refused || 0) > 0 || Number(s.unsigned || 0) > 0)) {
    return { verdict: "bad", words: `${name}'s deliveries are refused: ${Number(s.unsigned || 0) && !Number(s.refused || 0) ? "they carry no signature" : "the key they are signed with does not match the one saved here"}.` };
  }
  if (s && !Number(s.accepted || 0)) return { verdict: "wait", words: `Waiting for ${name}: no real delivery since the key was saved.` };
  if (t.state === "received") return { verdict: "ok", words: `Connected. The last delivery from ${name} came ${t.last_at ? `at ${hm(t.last_at)} UTC on ${String(t.last_at).slice(0, 10)}` : "recently"}.` };
  if (t.state === "missing" || t.state === "exposed") return { verdict: "bad", words: `${name} cannot be read yet: its signing secret is not saved here.` };
  if (t.state === "never" || t.state === "ready") return { verdict: "wait", words: `Waiting for ${name}: nothing has arrived yet.${t.test_at ? " Skald's own test worked." : ""}` };
  return { verdict: null, words: "" };
}
