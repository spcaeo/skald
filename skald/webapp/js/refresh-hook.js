// "Refresh now" from inside a card (#43): main.js owns the page's model and the recount, so it
// hands its function here once (setRefresh) and a card asks for it (refreshSite) without
// importing main.js. The answer: { ok, result, message } (data.js refresh()).

let run = null;

export function setRefresh(fn) { run = fn; }

export function refreshSite() {
  return run ? run() : Promise.resolve({ ok: false, message: "Refresh is not available on this page." });
}
