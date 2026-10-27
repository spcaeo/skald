// The words and the timing of a set-up's live progress (2.43, setup-live.js), as data: no DOM,
// so node runs it (tests/js/setup-live.mjs). The server's side: skald/setup_live.py.

// How often the page asks: every 5 s, every 30 s after 2 minutes; never while the tab is hidden.
export const POLL = { every: 5000, slowAfter: 120000, slow: 30000 };
export const delay = (elapsed) => (elapsed < POLL.slowAfter ? POLL.every : POLL.slow);

const hm = (iso) => (iso ? String(iso).slice(11, 16) : "");
const n = (x) => Number(x || 0).toLocaleString("en-GB");

/* The checklist's lines from sites/live's `steps`: {id, words, more, done, at}. */
export function itemsOf(live) {
  return (live?.steps || []).map((s) => {
    let more = "";
    if (s.id === "data" && s.done) {
      more = s.recent ? `${n(s.recent)} in the last 15 min, newest ${hm(s.newest_at)} UTC`
        : s.newest_at ? `none in the last 15 min; newest ${String(s.newest_at).slice(0, 16).replace("T", " ")} UTC` : "";
    }
    return { id: s.id, words: s.words, more, done: !!s.done, at: s.at || null };
  });
}

/* The site's state as a pill: [kind, words]. live: sites/live's one-site view, or one row of
   its {all: true} answer. */
export function pillOf(live) {
  const st = live?.state;
  if (st === "done") return live.recent ? ["good", "Receiving data"] : ["good", "Set up"];
  if (st === "receiving") return ["good", "Receiving data"];
  if (st === "waiting") return ["warn", "Waiting for data"];
  return null;
}

/* The done state's lines: the head and the invites' one line. */
export function doneWords(live, site) {
  const head = live?.recent ? `${site} is receiving data: ${n(live.recent)} lines in the last 15 minutes.`
    : `${site} is set up.`;
  const people = live?.invites_words || (live?.people ? `${live.people === 1 ? "1 person waits" : `${live.people} people wait`} for an invite.` : "");
  return { head, people };
}

/* The wizard's first two answers in the address (never an email or a name):
   org=same|<id>|new and ppl=<user id>.<user id>. */
export const orgValue = (choice) => (choice === "new" || choice === "same" || /^\d+$/.test(String(choice)) ? String(choice) : "same");
export function orgFrom(v) {
  const s = String(v || "");
  return s === "new" || /^\d{1,12}$/.test(s) ? s : "same";
}
export const pplValue = (ids) => [...new Set((ids || []).map(String).filter((x) => /^\d{1,12}$/.test(x)))].join(".");
export const pplFrom = (v) => String(v || "").split(".").filter((x) => /^\d{1,12}$/.test(x)).map(Number);

/* What sites/add gets from the two answers. people: [{user, role} | {email, role}]. */
export function addBody(o) {
  const org = orgValue(o?.org || "same");
  const body = org === "same" ? {} : { org };            // this organisation: nothing to say
  if (org === "new") { body.org_name = String(o.name || "").trim(); body.privacy_class = o.privacy === "client" ? "client" : "internal"; }
  const people = (o?.people || []).filter((p) => p && (p.user || p.email)).map((p) => ({ ...(p.user ? { user: p.user } : { email: String(p.email).trim() }), role: p.role || "viewer",
    ...(p.sees === "site" || p.sees === "all" ? { sees: p.sees } : {}) }));
  if (people.length) body.people = people;
  return body;
}

/* "Check now"'s answer box kind. */
export const checkKind = (v) => (v === "ok" ? "ok" : v === "bad" ? "bad" : "warn");
