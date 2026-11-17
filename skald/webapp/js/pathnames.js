// How much of a page's path the figures keep (#71): the same numbers as
// skald/path_names.py (a test holds the two equal).
//
//   PATH_CHARS       kept from #71 on: a page's path, no query, cut to this length
//   OLD_PATH_CHARS   what days counted before #71 kept
//   mayBeCut(path)   true for a site path of exactly OLD_PATH_CHARS characters: it may be
//                    a longer address cut short, so it is marked "may be cut short" and opens nothing
//                    (urlactions.js). A page whose address really is that long is marked
//                    too: the figures cannot tell the two apart.

export const PATH_CHARS = 512;
export const OLD_PATH_CHARS = 70;

export const CUT_MARK = "may be cut short";
export const CUT_WORDS = `On days counted before the update, Skald kept only the first ${OLD_PATH_CHARS} characters of a page's address, so this one may be cut short. It can be copied, not opened.`;

export function mayBeCut(path) {
  const t = typeof path === "string" ? path : "";
  return t.startsWith("/") && !t.startsWith("//") && t.length === OLD_PATH_CHARS;
}
