// Overview > Insights (#5, #6): the three plain lines of every card, in one place.
//
//   title   what is wrong
//   why     why it matters to the site's owner
//   act     what to do (shown after "Do:")
//
// No counts, percentages or dates: the figures stay in the card's Open view and on the
// other tabs. A number appears only where it IS the message ("3 pages lose their readers",
// "1 of 3 sitemaps is still missing"). Every word here comes from the to-do's own fields
// (todos.json: kind, figures, rows, recheck.still), never typed in for one site.
//
// search (#40) is the one kind not from the log: a stopped Search Console or Bing sync, with
// the day it stopped and the engine's own reason.
//
// status: open (to do), failed (marked fixed, the daily re-check still finds it), checking,
// passed. A leaving-pages card stands for every open leaving page together (group).

const NAME = { lost: "Old pages", markdown: "Markdown copies", sitemap: "Sitemaps", errors: "Server errors" };

const plural = (n, one, many) => (n === 1 ? one : many);

/* The source most of a group's visits came from: "search" when it is a search engine. */
function fromSearch(list) {
  const by = {};
  for (const t of list) for (const r of t.rows || []) by[r.source] = (by[r.source] || 0) + (Number(r.visits) || 0);
  const top = Object.entries(by).sort((a, b) => b[1] - a[1])[0];
  return Boolean(top && /search/i.test(top[0] || ""));
}

function leave(list, status) {
  const t = list[0];
  if (status === "open") {
    const n = list.length;
    return {
      title: `${n} ${plural(n, "page loses its readers", "pages lose their readers")}`,
      why: `People land here${fromSearch(list) ? " from search" : ""} and leave without a next step.`,
      act: `Add a clear next step on ${plural(n, "the page", "each page")}.`,
    };
  }
  if (status === "failed") {
    return { title: `${t.subject} still loses its readers`, why: "Visitors still leave after this page, without a next step.",
      act: "Try a clearer next step near the top of the page." };
  }
  return null;
}

function lost(t, status) {
  if (status === "open") {
    return { title: "Old pages answer \"Page not found\"", why: "Visitors and crawlers who follow old links land nowhere.",
      act: "Redirect each to the closest live page, or answer 410 gone." };
  }
  if (status !== "failed") return null;
  // The addresses only bots ask for are named apart and never the message (#23).
  const bots = new Set(t.recheck?.bots_only || []);
  const still = (t.recheck?.still || []).filter(([path]) => !bots.has(path));
  const k = (t.recheck?.still_total ?? still.length) - bots.size;
  const top = still[0]?.[0];
  const target = top ? (t.rows || []).find((r) => r.path === top)?.target : null;
  const most = k > 1 ? " first: it is asked for most since your fix" : "";
  return {
    title: k === 1 ? "An old page still answers \"Page not found\"" : "Old pages still answer \"Page not found\"",
    why: "Visitors and crawlers who follow the old links still land nowhere.",
    act: !top ? "Redirect the ones still asked for to the closest live page." : target ? `Redirect ${top} to ${target}${most}.`
      : `Redirect ${top} to a live page, or answer 410 gone${k > 1 ? " (it is asked for most since your fix)" : ""}.`,
  };
}

function markdown(t, status) {
  const why = "AI assistants ask for a .md copy to read a page, and get \"Page not found\".";
  const act = "Serve a Markdown copy at each .md address, or redirect it to the page.";
  if (status === "open") return { title: "AI tools can't get the Markdown copies of your pages", why, act };
  if (status === "failed") return { title: "AI tools still can't get some Markdown copies", why, act };
  return null;
}

function sitemap(t, status) {
  if (status === "open") {
    const one = (t.figures?.paths ?? 1) === 1;
    return { title: one ? "A sitemap crawlers ask for is missing" : "Sitemaps crawlers ask for are missing",
      why: "Search engines and AI crawlers use sitemaps to find your pages.",
      act: one ? "Publish it, or redirect it to the sitemap you have." : "Publish them, or redirect them to the sitemap you have." };
  }
  if (status !== "failed") return null;
  const still = t.recheck?.still || [];
  const k = t.recheck?.still_total ?? still.length;
  if (!k) {                     // a file written before #5 names no address: say it plainly
    return { title: "Sitemaps crawlers ask for are still missing", why: "Crawlers keep asking for them and find nothing.",
      act: "Publish them, or redirect them to your sitemap." };
  }
  const of = Math.max(t.figures?.paths ?? 0, k);
  return {
    title: `${k} of ${of} ${plural(of, "sitemap", "sitemaps")} ${plural(k, "is", "are")} still missing`,
    why: k === 1 && still[0] ? `Crawlers keep asking for ${still[0][0]} and find nothing.` : "Crawlers keep asking for them and find nothing.",
    act: k === 1 ? "Publish it, or redirect it to your sitemap." : "Publish them, or redirect them to your sitemap.",
  };
}

function errors(t, status) {
  const why = t.figures?.people ? "People who ask for them get an error page." : "Only bots met them so far; people could be next.";
  if (status === "open") return { title: "Your server fails to answer some pages", why, act: "Send the list to your developer or host." };
  if (status === "failed") return { title: "Server errors came back after your fix", why, act: "Send the addresses still failing to your developer or host." };
  return null;
}

/* #40: a search sync that worked, then failed for a day. Not from the log: the day it
   stopped and the engine's own reason ARE the message. It goes by itself after a good sync. */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dayOf = (ts) => { const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(ts || ""); return m ? `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}` : ""; };

function search(t, status) {
  if (status !== "open") return null;
  const f = t.figures || {};
  const since = dayOf(f.since);
  return { title: `${f.engine === "bing" ? "Bing Webmaster Tools" : "Search Console"} stopped syncing${since ? ` on ${since}` : ""}`,
    why: `${f.reason || "The engine gave no reason"}. Your search figures stop there.`, act: t.todo || "Open the settings and reconnect." };
}

const BY_KIND = { lost, markdown, sitemap, errors, search };

/* The three lines of a card: list is the card's to-dos (one, or every open leaving page). */
export function cardWords(list, status) {
  const t = list[0];
  const got = t.kind === "leave" ? leave(list, status) : BY_KIND[t.kind]?.(t, status);
  if (got) return got;
  const name = t.kind === "leave" ? t.subject : NAME[t.kind] || t.title;
  if (status === "passed") {
    return { title: `${name}: your fix worked`, why: "The problem has not come back in your log since your fix.", act: "Nothing to do." };
  }
  return { title: `${name}: checking your fix`, why: "Skald counts the same problem in your log on every whole day after your fix.",
    act: "Nothing to do now." };
}
