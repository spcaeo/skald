// SKALD-49: AI fetches as pages, with files counted apart. An AI crawler fetches images,
// styles, scripts, robots.txt and sitemaps as well as pages, and every one of those is a
// request. The figures that say "pages" count pages only; the rest is one "files" number
// beside them. Both come from `ai_formats` (ai_formats.py, audited by audit_ai_formats.py):
// per tier, "Page" is the pages and every other format the files, so pages + files is
// exactly the tier's requests. A range with a day collected before 18 Oct 2026 has no
// split: the figures say "requests" there, never a page count made of some of the days.

// The same rule as ai_formats.format_of (parse.ASSET, parse.BEACON), for the feed's rows.
// tests/test_ai_split.py runs both over the same paths.
const ASSET = new RegExp(
  "\\.(css|js|mjs|map|png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|eot|txt|xml|json|webmanifest"
  + "|xsl|xslt|rss|atom|csv|tsv|pdf|zip|gz|tgz|rar|7z|mp4|webm|mov|mp3|wav|ogg|m4a"
  + "|docx?|xlsx?|pptx?|wasm)$|^/_next/|^/static/|^/assets/|^/_nuxt/|^/build/", "i");
const BEACON = /^\/(?:api(?:\/|$)|(?:__analytics|collect|beacon|ping)\b)/i;
const RSC = /[?&](_rsc|__flight__|_data)=/i;

export const FILE_WORDS = "robots.txt, sitemaps, llms.txt, images, styles and scripts";

/* One of ai_formats.FORMATS for a path (a query string, if any, decides a payload). */
export function formatOf(path) {
  const raw = String(path || "");
  const low = raw.split("#", 1)[0].split("?", 1)[0].toLowerCase();
  const name = low.slice(low.lastIndexOf("/") + 1);
  if (low === "/llms.txt" || low === "/llms-full.txt") return "llms.txt";
  if (low === "/robots.txt") return "robots.txt";
  if (name.endsWith(".md") || name.endsWith(".mdx")) return "Markdown";
  if (name.startsWith("sitemap") && name.endsWith(".xml")) return "Sitemap";
  if (name.endsWith(".txt")) return "Text";
  if (ASSET.test(low) || BEACON.test(low) || RSC.test(raw)) return "Other file";
  return "Page";
}

export const isPageFetch = (path) => formatOf(path) === "Page";

const sum = (o) => Object.values(o || {}).reduce((a, v) => a + (v || 0), 0);

/* {pages, files, requests} of one tier for a range's totals (or today's figures), or null
   when the range has a day without the split. */
export function aiSplit(t, tier) {
  const f = t?.ai_formats?.[tier]?.formats;
  if (!f || t.unmeasured?.ai_formats) return null;
  const requests = sum(f), pages = f.Page || 0;
  return { pages, files: requests - pages, requests };
}

/* {pages: {name: n}, files: {name: n}} of one tier by name, or null as aiSplit. The day keeps
   20 names and folds the rest into "(all others)" (ai_formats.TOP). */
export function aiSplitByName(t, tier) {
  const by = t?.ai_formats?.[tier]?.by_name;
  if (!by || t.unmeasured?.ai_formats) return null;
  const pages = {}, files = {};
  for (const [name, c] of Object.entries(by)) {
    const all = sum(c), p = c.Page || 0;
    if (!all) continue;
    pages[name] = p;
    files[name] = all - p;
  }
  return { pages, files };
}

/* The words under a pages figure: "+ 412 files (robots.txt, ...)". */
export function filesWords(split, n) {
  return split.files ? `+ ${n(split.files)} file${split.files === 1 ? "" : "s"} (${FILE_WORDS})` : "no files";
}
