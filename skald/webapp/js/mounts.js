// Components that listen outside their own element (the window's resize, Back and
// Forward) are torn down once a redraw drops them, so redraws never pile listeners
// up on detached copies. foldertabs.js and grid.js register here; main.js may call
// sweep() before each render too.

const LIVE = new Set();

// An instance built but not yet on the page is spared: a render may build several
// before it attaches any. One that was on the page and left it goes at the next
// sweep; one never attached goes once it is a few seconds old.
const STALE_MS = 5000;

export function sweep() {
  const now = Date.now();
  for (const it of LIVE) {
    if (it.host.isConnected) { it.seen = true; continue; }
    if (!it.seen && now - it.born < STALE_MS) continue;
    LIVE.delete(it);
    try { it.destroy(); } catch (e) { console.error(e); }
  }
}

// Register one instance; returns its own teardown (safe to call twice).
export function track(host, destroy) {
  sweep();
  const it = { host, destroy, born: Date.now(), seen: false };
  LIVE.add(it);
  requestAnimationFrame(() => { if (host.isConnected) it.seen = true; });
  return () => { if (LIVE.delete(it)) destroy(); };
}

// How many are alive: for tests.
export const liveCount = () => LIVE.size;

// A route change redraws the panel; sweep once the old copies have gone.
for (const type of ["hashchange", "popstate"]) addEventListener(type, () => setTimeout(sweep, 0));
