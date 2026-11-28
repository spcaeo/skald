// What a table's search box looks for (SKALD-70): the words as typed, and, when they are an
// address on this site (https://www.example.com/blog/x/, or www.example.com/blog/x/ without
// the scheme), that address's path too, so a page pasted from the browser finds its row.
//
// The path of an address is looked for at the start of a cell (a pasted address names one
// page: https://www.example.com/blog/ never finds /en-us/blog/); the words as typed are looked
// for anywhere, as before. Callers pass a cell's text, or a row's cells joined by SEP.
//
// One of the site's own hosts only: app.json `hosts`, the site's name, and each with and
// without "www.". An address on another site stays plain text (it finds a row only where a
// cell shows it). A #fragment is dropped. A ?query is kept where a cell shows the path with a
// query; a row with no such cell matches the path without it.
//
// grid.js and table.js both search through searchTest(), so every table with a page column
// (Pages, landing pages, Search › Pages, Agent files, Not found, the leaderboard) reads it.

let HOSTS = new Set();
export const SEP = "\u0001";              // between a row's cells in grid.js's search text

/* The site's hosts, from app.json (main.js, at each load). */
export function setSearchHosts(site, hosts = []) {
  const out = new Set();
  for (const raw of [site, ...(hosts || [])]) {
    const name = String(raw || "").trim().toLowerCase().replace(/^[a-z][a-z0-9+.-]*:\/\//, "").replace(/[/:].*$/, "");
    if (!name) continue;
    out.add(name);
    out.add(name.startsWith("www.") ? name.slice(4) : `www.${name}`);
  }
  HOSTS = out;
}

const ADDRESS = /^(?:https?:\/\/)?([a-z0-9.-]+)(?::\d+)?(\/[^\s]*)?$/i;

/* {raw, path, bare} for a query (lower case): `path` and `bare` only for an address on this
   site (`bare` without the ?query). Null for an empty query. */
export function searchWords(q) {
  const raw = String(q ?? "").trim().toLowerCase();
  if (!raw) return null;
  const m = ADDRESS.exec(raw);
  const scheme = /^https?:\/\//.test(raw);
  if (!m || !HOSTS.has(m[1]) || (!scheme && !m[2])) return { raw, path: null, bare: null };
  const path = (m[2] || "/").split("#")[0] || "/";
  return { raw, path, bare: path.split("?")[0] || "/" };
}

/* Does a cell start with this page path? The home page "/" only as the whole cell (or with a
   query): every path starts with "/". A path with a closing "/" also finds the same path
   shown without it (/pricing/ finds /pricing), as Skald treats them as one page. */
function startsCell(cell, path) {
  if (path === "/") return cell === "/" || cell.startsWith("/?");
  if (cell.startsWith(path)) return true;
  const bare = path.endsWith("/") ? path.slice(0, -1) : null;
  return !!bare && (cell === bare || cell.startsWith(`${bare}?`));
}

/* A test for a cell's text, or a row's cells joined by SEP (lower case); null when there is
   nothing to look for. An address's path must start a cell; a ?query is kept where a cell
   shows the path with a query. */
export function searchTest(q) {
  const w = searchWords(q);
  if (!w) return null;
  return (text) => {
    if (text.includes(w.raw)) return true;
    if (w.path == null) return false;
    const cells = text.split(SEP);
    if (cells.some((c) => startsCell(c, w.path))) return true;
    if (w.bare === w.path) return false;
    // A pasted ?query: a row that shows this path with another query is not it.
    return cells.some((c) => startsCell(c, w.bare)) && !cells.some((c) => c.startsWith(`${w.bare}?`));
  };
}
